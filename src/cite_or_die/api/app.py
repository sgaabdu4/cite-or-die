import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import SecretStr

from cite_or_die import __version__
from cite_or_die.api.diligence import router as diligence_router
from cite_or_die.auth.jwt import get_auth_context, issue_token
from cite_or_die.core.config import Settings, get_settings
from cite_or_die.core.models import (
    AuditEvent,
    AuditEventType,
    AuthContext,
    ChatRequest,
    ChatResponse,
    DocumentChunk,
    DocumentRecord,
    HealthStatus,
    ProviderConfigInput,
    ProviderConfigStatus,
    ProviderConfigStored,
    ProviderConnectionTestResult,
    Role,
    UploadResponse,
)
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.observability.metrics import CHAT_LATENCY, CHATS, UPLOADS, metrics_response
from cite_or_die.observability.tracing import setup_tracing
from cite_or_die.providers.network import safe_async_transport_for_url
from cite_or_die.providers.url_policy import provider_base_url_error, provider_is_hosted
from cite_or_die.security.pseudonymization import (
    InvalidPseudonymMapError,
    pseudonym_scope_operation_lock,
    pseudonymize_chunks_for_matter_read_only,
    validate_pseudonym_scope_ids,
)
from cite_or_die.security.runtime_config import (
    InvalidTenantIdError,
    ProviderConfigUnreadableError,
    effective_provider_config,
    is_gemini_base_url,
    provider_default_model,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.service = CiteOrDieService(settings)
    yield


app = FastAPI(title="cite-or-die", version=__version__, lifespan=lifespan)
setup_tracing(app, Settings())
app.mount("/static", StaticFiles(packages=[("cite_or_die", "ui")]), name="static")
app.include_router(diligence_router)

_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


def get_service(request: Request) -> CiteOrDieService:
    return cast(CiteOrDieService, request.app.state.service)


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    from importlib.resources import files

    return files("cite_or_die.ui").joinpath("index.html").read_text(encoding="utf-8")


@app.get("/healthz")
async def healthz() -> HealthStatus:
    return HealthStatus(status="ok", version=__version__)


@app.get("/readyz")
async def readyz(service: CiteOrDieService = Depends(get_service)) -> HealthStatus:
    vector_ready = await service.retrieval.vector_store.ready()
    return HealthStatus(
        status="ok" if vector_ready and service.audit.verify_chain() else "degraded",
        version=__version__,
        dependencies={
            "vector_store": "ok" if vector_ready else "down",
            "audit_chain": "ok" if service.audit.verify_chain() else "tampered",
        },
    )


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics_response().decode("utf-8"))


@app.post("/dev/token")
async def dev_token(
    tenant_id: str = Form(default="dev"),
    matter_id: str = Form(default="m_default"),
    subject: str = Form(default="dev-user"),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if settings.app_env == "prod":
        raise HTTPException(status_code=404, detail="dev token endpoint disabled in prod")
    token = issue_token(tenant_id, subject, [Role.admin], settings, matter_id)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    tenant_id: str | None = Form(default=None),
    matter_id: str | None = Form(default=None),
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> UploadResponse:
    data = await _read_limited_upload(file, service.settings.max_upload_mb * 1024 * 1024)
    response = await service.upload(
        ctx,
        file.filename or "upload.bin",
        file.content_type or "application/octet-stream",
        data,
        tenant_id,
        matter_id,
    )
    UPLOADS.labels(response.document.tenant_id).inc()
    return response


async def _read_limited_upload(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        remaining = max_bytes - total
        read_size = min(_UPLOAD_READ_CHUNK_BYTES, max(remaining + 1, 1))
        chunk = await file.read(read_size)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"upload exceeds {max_bytes // (1024 * 1024)} MB",
            )
        chunks.append(chunk)


@app.post("/chat")
async def chat(
    request: ChatRequest,
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> ChatResponse:
    start = time.perf_counter()
    response = await service.chat(ctx, request)
    CHAT_LATENCY.observe(time.perf_counter() - start)
    CHATS.labels(response.tenant_id, "ok").inc()
    return response


@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        try:
            response = await service.chat(ctx, request)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Chat request failed."
            yield f"event: error\ndata: {json.dumps({'message': detail})}\n\n"
            return
        except Exception:
            yield 'event: error\ndata: {"message":"Chat request failed."}\n\n'
            return
        yield f"event: answer\ndata: {response.model_dump_json()}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/docs/list")
async def list_docs(
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> list[DocumentRecord]:
    service.authorizer.require(ctx, "read", ctx.tenant_id)
    return service.repository.list_documents(ctx.tenant_id, ctx.matter_id)


@app.get("/docs/{doc_id}/file")
async def get_doc_file(
    doc_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> PlainTextResponse:
    service.authorizer.require(ctx, "read", ctx.tenant_id, ctx.matter_id)
    _safe_pseudonym_scope(ctx)
    async with pseudonym_scope_operation_lock(service.settings, ctx.tenant_id, ctx.matter_id):
        _find_scoped_document(service, ctx, doc_id)
        evidence_path = service.settings.uploads_path / "evidence" / f"{doc_id}.txt"
        if evidence_path.exists():
            return PlainTextResponse(
                evidence_path.read_text(encoding="utf-8"),
                media_type="text/plain",
            )
        chunks = service.repository.list_chunks(ctx.tenant_id, ctx.matter_id, doc_ids=[doc_id])
        if not chunks:
            raise HTTPException(status_code=404, detail="source file not found")
        try:
            chunks = pseudonymize_chunks_for_matter_read_only(
                chunks,
                settings=service.settings,
                tenant_id=ctx.tenant_id,
                matter_id=ctx.matter_id,
                create_ephemeral_entities=False,
            )
        except InvalidPseudonymMapError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return PlainTextResponse(
            _chunk_evidence_text(chunks),
            media_type="text/plain",
        )


@app.get("/docs/{doc_id}/raw")
async def get_doc_raw(
    doc_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> FileResponse:
    service.authorizer.require(ctx, "read", ctx.tenant_id, ctx.matter_id)
    document = _find_scoped_document(service, ctx, doc_id)
    source_path = next(
        (item for item in service.settings.uploads_path.glob(f"{doc_id}.*") if item.is_file()),
        None,
    )
    if source_path is None:
        raise HTTPException(status_code=404, detail="source file not found")
    return FileResponse(source_path, media_type=document.content_type, filename=document.filename)


def _find_scoped_document(
    service: CiteOrDieService, ctx: AuthContext, doc_id: str
) -> DocumentRecord:
    document = next(
        (
            item
            for item in service.repository.list_documents(ctx.tenant_id, ctx.matter_id)
            if item.doc_id == doc_id
        ),
        None,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


def _chunk_evidence_text(chunks: list[DocumentChunk]) -> str:
    parts = []
    for chunk in chunks:
        body = chunk.text.strip()
        if not body:
            continue
        label = f"Page {chunk.page}" if chunk.page is not None else f"Chunk {chunk.ordinal + 1}"
        parts.append(f"{label}\n{body}")
    return "\n\n".join(parts)


def _require_admin(ctx: AuthContext) -> None:
    if Role.admin not in ctx.roles:
        raise HTTPException(status_code=403, detail="admin role required")


def _safe_tenant(ctx: AuthContext) -> str:
    try:
        from cite_or_die.security.runtime_config import _validate_tenant_id

        _validate_tenant_id(ctx.tenant_id)
    except InvalidTenantIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ctx.tenant_id


def _safe_pseudonym_scope(ctx: AuthContext) -> None:
    try:
        validate_pseudonym_scope_ids(ctx.tenant_id, ctx.matter_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _provider_config_unreadable(exc: ProviderConfigUnreadableError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


def _load_provider_config(
    service: CiteOrDieService,
    tenant: str,
) -> ProviderConfigStored | None:
    try:
        return service.runtime_config.load(tenant)
    except ProviderConfigUnreadableError as exc:
        raise _provider_config_unreadable(exc) from exc


@app.get("/settings/provider")
async def get_provider_settings(
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> ProviderConfigStatus:
    tenant = _safe_tenant(ctx)
    try:
        status = service.runtime_config.status(tenant)
    except ProviderConfigUnreadableError as exc:
        raise _provider_config_unreadable(exc) from exc
    if status is None:
        raise HTTPException(status_code=404, detail="provider config not set")
    return status


@app.put("/settings/provider")
async def put_provider_settings(
    config: ProviderConfigInput,
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> ProviderConfigStatus:
    tenant = _safe_tenant(ctx)
    has_existing = service.runtime_config.has_config(tenant)
    if has_existing and Role.admin not in ctx.roles:
        raise HTTPException(
            status_code=403,
            detail="admin role required to update an existing provider config",
        )
    if not has_existing:
        service.authorizer.require(ctx, "upload", tenant)
    previous = _load_provider_config(service, tenant) if has_existing else None
    effective = effective_provider_config(config, previous, service.settings)
    base_url_error = _provider_config_base_url_error(effective, service.settings)
    if base_url_error is not None:
        raise HTTPException(status_code=400, detail=base_url_error)
    model = effective.llm_model or provider_default_model(
        effective.llm_provider,
        effective.llm_base_url,
    )
    blocked = _hosted_provider_block(effective, service.settings, model)
    if blocked is not None:
        raise HTTPException(status_code=400, detail=blocked.detail)
    if (
        _provider_config_requires_api_key(effective)
        and config.llm_api_key is None
        and not _can_reuse_saved_provider_key(previous, effective)
    ):
        raise HTTPException(
            status_code=400,
            detail=f"{config.llm_provider} provider requires an api_key",
        )
    status, requires_reindex = service.runtime_config.save(tenant, effective, ctx.subject)
    service.invalidate_runtime_config(tenant)
    service.audit.append(
        AuditEvent(
            tenant_id=tenant,
            actor=ctx.subject,
            event_type=AuditEventType.runtime_config_changed,
            payload={
                "action": "set",
                "llm_provider": status.llm_provider,
                "llm_model": status.llm_model,
                "llm_base_url": status.llm_base_url,
                "fingerprint": status.llm_api_key_fingerprint,
                "embedding_provider": status.embedding_provider,
                "embedding_dim": status.embedding_dim,
                "reranker_provider": status.reranker_provider,
                "requires_reindex": requires_reindex,
            },
        )
    )
    return status


@app.post("/settings/provider/reindex")
async def reindex_provider_sources(
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> ProviderConfigStatus:
    _require_admin(ctx)
    tenant = _safe_tenant(ctx)
    if _load_provider_config(service, tenant) is None:
        raise HTTPException(status_code=404, detail="provider config not set")
    indexed_chunks = await service.reindex_tenant_sources(tenant)
    try:
        status = service.runtime_config.clear_reindex_required(tenant)
    except ProviderConfigUnreadableError as exc:
        raise _provider_config_unreadable(exc) from exc
    if status is None:
        raise HTTPException(status_code=404, detail="provider config not set")
    service.audit.append(
        AuditEvent(
            tenant_id=tenant,
            actor=ctx.subject,
            event_type=AuditEventType.runtime_config_changed,
            payload={"action": "reindex", "chunk_count": indexed_chunks},
        )
    )
    return status


@app.post("/settings/provider/test")
async def test_provider_settings(
    config: ProviderConfigInput | None = None,
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> ProviderConnectionTestResult:
    tenant = _safe_tenant(ctx)
    has_existing = service.runtime_config.has_config(tenant)
    if has_existing and Role.admin not in ctx.roles:
        raise HTTPException(
            status_code=403,
            detail="admin role required to test an existing provider config",
        )
    effective = _provider_test_config(config, service, tenant, has_existing)
    return await _test_provider_connection(effective, service.settings)


@app.delete("/settings/provider")
async def delete_provider_settings(
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> dict[str, bool]:
    _require_admin(ctx)
    tenant = _safe_tenant(ctx)
    deleted = service.runtime_config.delete(tenant)
    service.invalidate_runtime_config(tenant)
    if deleted:
        service.audit.append(
            AuditEvent(
                tenant_id=tenant,
                actor=ctx.subject,
                event_type=AuditEventType.runtime_config_changed,
                payload={"action": "delete"},
            )
        )
    return {"deleted": deleted}


def _provider_test_config(
    config: ProviderConfigInput | None,
    service: CiteOrDieService,
    tenant: str,
    has_existing: bool,
) -> ProviderConfigInput:
    stored = _load_provider_config(service, tenant) if has_existing else None
    if config is None:
        if stored is None:
            raise HTTPException(status_code=404, detail="provider config not set")
        return _stored_provider_to_input(stored)
    if (
        config.llm_api_key is None
        and stored is not None
        and _can_reuse_saved_provider_key(stored, config)
        and stored.llm_api_key_plaintext is not None
    ):
        config = config.model_copy(update={"llm_api_key": SecretStr(stored.llm_api_key_plaintext)})
    return effective_provider_config(config, stored, service.settings)


def _stored_provider_to_input(stored: ProviderConfigStored) -> ProviderConfigInput:
    return ProviderConfigInput(
        llm_provider=stored.llm_provider,
        llm_model=stored.llm_model,
        llm_base_url=stored.llm_base_url,
        llm_api_key=(
            SecretStr(stored.llm_api_key_plaintext)
            if stored.llm_api_key_plaintext is not None
            else None
        ),
        embedding_provider=stored.embedding_provider,
        embedding_dim=stored.embedding_dim,
        reranker_provider=stored.reranker_provider,
    )


async def _test_provider_connection(
    config: ProviderConfigInput,
    settings: Settings,
) -> ProviderConnectionTestResult:
    model = config.llm_model or provider_default_model(config.llm_provider, config.llm_base_url)
    base_url_error = _provider_config_base_url_error(config, settings)
    if base_url_error is not None:
        return _provider_test_error(config, model, base_url_error)
    blocked = _hosted_provider_block(config, settings, model)
    if blocked is not None:
        return blocked
    request = _provider_test_request(config, model, settings)
    if request is None:
        return ProviderConnectionTestResult(
            ok=True,
            llm_provider=config.llm_provider,
            llm_model=model,
            detail="Offline provider ready.",
        )
    if isinstance(request, ProviderConnectionTestResult):
        return request
    try:
        await _post_provider_test_json(*request)
    except httpx.HTTPStatusError as exc:
        return ProviderConnectionTestResult(
            ok=False,
            llm_provider=config.llm_provider,
            llm_model=model,
            detail=f"Provider returned HTTP {exc.response.status_code}.",
        )
    except httpx.HTTPError:
        return ProviderConnectionTestResult(
            ok=False,
            llm_provider=config.llm_provider,
            llm_model=model,
            detail="Provider could not be reached.",
        )
    return ProviderConnectionTestResult(
        ok=True,
        llm_provider=config.llm_provider,
        llm_model=model,
        detail="Provider connection verified.",
    )


def _hosted_provider_block(
    config: ProviderConfigInput,
    settings: Settings,
    model: str,
) -> ProviderConnectionTestResult | None:
    if not provider_is_hosted(
        config.llm_provider,
        config.llm_base_url,
        settings.provider_base_url_allowed_hosts,
    ):
        return None
    if settings.app_env == "prod" and not settings.allow_hosted_llm:
        return ProviderConnectionTestResult(
            ok=False,
            llm_provider=config.llm_provider,
            llm_model=model,
            detail="Hosted model providers are blocked in production.",
        )
    return None


def _provider_test_request(
    config: ProviderConfigInput,
    model: str,
    settings: Settings,
) -> tuple[str, dict[str, str], dict[str, object]] | ProviderConnectionTestResult | None:
    api_key = config.llm_api_key.get_secret_value() if config.llm_api_key is not None else None
    if config.llm_provider == "fake":
        return None
    if config.llm_provider == "openai":
        if not api_key:
            return _missing_key(config, model, "OpenAI API key required.")
        return (
            "https://api.openai.com/v1/responses",
            {"Authorization": f"Bearer {api_key}"},
            {
                "model": model,
                "input": "Reply with the single word OK.",
                "max_output_tokens": 8,
            },
        )
    if config.llm_provider == "anthropic":
        if not api_key:
            return _missing_key(config, model, "Anthropic API key required.")
        return (
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            {
                "model": model,
                "max_tokens": 8,
                "messages": [{"role": "user", "content": "Reply with OK."}],
            },
        )
    if config.llm_provider == "openai-compatible":
        base_url = (config.llm_base_url or "").rstrip("/")
        base_url_error = _provider_base_url_error(config.llm_provider, base_url, settings)
        if base_url_error is not None:
            return _provider_test_error(config, model, base_url_error)
        if is_gemini_base_url(base_url) and not api_key:
            return _missing_key(config, model, "Gemini API key required.")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        return (
            f"{base_url}/chat/completions",
            headers,
            {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with OK."}],
                "max_tokens": 8,
                "temperature": 0,
            },
        )
    if config.llm_provider == "ollama":
        base_url = (config.llm_base_url or "http://localhost:11434").rstrip("/")
        base_url_error = _provider_base_url_error(config.llm_provider, base_url, settings)
        if base_url_error is not None:
            return _provider_test_error(config, model, base_url_error)
        return (
            f"{base_url}/api/generate",
            {},
            {"model": model, "prompt": "Reply with OK.", "stream": False},
        )
    return None


def _provider_test_error(
    config: ProviderConfigInput,
    model: str,
    detail: str,
) -> ProviderConnectionTestResult:
    return ProviderConnectionTestResult(
        ok=False,
        llm_provider=config.llm_provider,
        llm_model=model,
        detail=detail,
    )


def _missing_key(
    config: ProviderConfigInput, model: str, detail: str
) -> ProviderConnectionTestResult:
    return ProviderConnectionTestResult(
        ok=False,
        llm_provider=config.llm_provider,
        llm_model=model,
        detail=detail,
    )


def _provider_config_base_url_error(
    config: ProviderConfigInput,
    settings: Settings,
) -> str | None:
    if config.llm_provider == "openai-compatible":
        return _provider_base_url_error(config.llm_provider, config.llm_base_url or "", settings)
    if config.llm_provider == "ollama":
        return _provider_base_url_error(config.llm_provider, config.llm_base_url or "", settings)
    return None


def _provider_config_requires_api_key(config: ProviderConfigInput) -> bool:
    if config.llm_provider in {"anthropic", "openai"}:
        return True
    if config.llm_provider == "openai-compatible":
        return is_gemini_base_url(config.llm_base_url or "")
    return False


def _provider_base_url_error(provider: str, base_url: str, settings: Settings) -> str | None:
    return provider_base_url_error(provider, base_url, settings.provider_base_url_allowed_hosts)


def _can_reuse_saved_provider_key(
    previous: ProviderConfigStored | None,
    config: ProviderConfigInput,
) -> bool:
    if previous is None or previous.llm_api_key_plaintext is None:
        return False
    if previous.llm_provider != config.llm_provider:
        return False
    if config.llm_provider != "openai-compatible":
        return True
    new_base_url = (config.llm_base_url or previous.llm_base_url or "").rstrip("/")
    old_base_url = (previous.llm_base_url or "").rstrip("/")
    return bool(old_base_url) and new_base_url == old_base_url


async def _post_provider_test_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
) -> None:
    async with httpx.AsyncClient(
        timeout=20,
        transport=safe_async_transport_for_url(url),
    ) as client:
        response = await client.post(url, headers=headers, json=payload)
    response.raise_for_status()


def create_app() -> FastAPI:
    return app
