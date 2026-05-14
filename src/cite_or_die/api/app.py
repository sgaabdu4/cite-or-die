import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from cite_or_die import __version__
from cite_or_die.auth.jwt import get_auth_context, issue_token
from cite_or_die.core.config import Settings, get_settings
from cite_or_die.core.models import (
    AuthContext,
    ChatRequest,
    ChatResponse,
    DocumentRecord,
    HealthStatus,
    Role,
    UploadResponse,
)
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.observability.metrics import CHAT_LATENCY, CHATS, UPLOADS, metrics_response
from cite_or_die.observability.tracing import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_tracing(app, settings)
    app.state.service = CiteOrDieService(settings)
    yield


app = FastAPI(title="cite-or-die", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(packages=[("cite_or_die", "ui")]), name="static")


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
    subject: str = Form(default="dev-user"),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if settings.app_env == "prod":
        return {"error": "dev token endpoint disabled in prod"}
    token = issue_token(tenant_id, subject, [Role.admin], settings)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    tenant_id: str | None = Form(default=None),
    ctx: AuthContext = Depends(get_auth_context),
    service: CiteOrDieService = Depends(get_service),
) -> UploadResponse:
    data = await file.read()
    response = await service.upload(
        ctx,
        file.filename or "upload.bin",
        file.content_type or "application/octet-stream",
        data,
        tenant_id,
    )
    UPLOADS.labels(response.document.tenant_id).inc()
    return response


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
    return service.repository.list_documents(ctx.tenant_id)


def create_app() -> FastAPI:
    return app
