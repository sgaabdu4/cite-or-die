import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from cite_or_die import __version__
from cite_or_die.auth.jwt import get_auth_context, issue_token
from cite_or_die.core.config import Settings, get_settings
from cite_or_die.core.models import (
    AuditEvent,
    AuditEventType,
    AuthContext,
    ChatRequest,
    ChatResponse,
    DocumentRecord,
    HealthStatus,
    ProviderConfigInput,
    ProviderConfigStatus,
    Role,
    UploadResponse,
)
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.observability.metrics import CHAT_LATENCY, CHATS, UPLOADS, metrics_response
from cite_or_die.observability.tracing import setup_tracing
from cite_or_die.security.runtime_config import InvalidTenantIdError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.service = CiteOrDieService(settings)
    yield


app = FastAPI(title="cite-or-die", version=__version__, lifespan=lifespan)
setup_tracing(app, Settings())
app.mount("/static", StaticFiles(packages=[("cite_or_die", "ui")]), name="static")

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
        response = await service.chat(ctx, request)
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
) -> FileResponse:
    service.authorizer.require(ctx, "read", ctx.tenant_id, ctx.matter_id)
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
    source_path = next(service.settings.uploads_path.glob(f"{doc_id}.*"), None)
    if source_path is None:
        raise HTTPException(status_code=404, detail="source file not found")
    return FileResponse(source_path, media_type=document.content_type, filename=document.filename)


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


@app.get("/settings/provider")
async def get_provider_settings(
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> ProviderConfigStatus:
    tenant = _safe_tenant(ctx)
    status = service.runtime_config.status(tenant)
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
    hosted = {"anthropic", "openai"}
    if config.llm_provider in hosted and config.llm_api_key is None and not has_existing:
        raise HTTPException(
            status_code=400,
            detail=f"{config.llm_provider} provider requires an api_key on first setup",
        )
    status, requires_reindex = service.runtime_config.save(tenant, config, ctx.subject)
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


def create_app() -> FastAPI:
    return app
