import asyncio
from pathlib import Path

import typer
import uvicorn
from rich import print

from cite_or_die.auth.jwt import issue_token
from cite_or_die.core.config import Settings
from cite_or_die.core.models import AuthContext, ChatRequest, Role
from cite_or_die.core.service import CiteOrDieService

app = typer.Typer(no_args_is_help=True)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8765, reload: bool = False) -> None:
    """Run the API and web UI."""

    uvicorn.run("cite_or_die.api.app:app", host=host, port=port, reload=reload)


@app.command()
def token(tenant: str = "dev", subject: str = "dev-user") -> None:
    """Issue a local development bearer token."""

    print(issue_token(tenant, subject, [Role.admin], Settings()))


@app.command()
def ingest(path: Path, tenant: str = "dev") -> None:
    """Ingest one local document using the deterministic local stack."""

    settings = Settings()
    service = CiteOrDieService(settings)
    ctx = AuthContext(tenant_id=tenant, subject="cli", roles=[Role.admin])
    response = asyncio.run(
        service.upload(ctx, path.name, "application/octet-stream", path.read_bytes())
    )
    print(response.model_dump())


@app.command()
def chat(question: str, tenant: str = "dev") -> None:
    """Ask a question against the tenant-local corpus."""

    settings = Settings()
    service = CiteOrDieService(settings)
    ctx = AuthContext(tenant_id=tenant, subject="cli", roles=[Role.admin])
    response = asyncio.run(service.chat(ctx, ChatRequest(question=question)))
    print(response.model_dump())
