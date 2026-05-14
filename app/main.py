"""FastAPI compatibility entrypoint for `uvicorn app.main:app`."""

from cite_or_die.api.app import app

__all__ = ["app"]
