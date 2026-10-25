import asyncio
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

import uvicorn
from fastapi import FastAPI
from typing_extensions import override

from cite_or_die.api.app import app, get_service
from cite_or_die.core.config import get_settings
from cite_or_die.core.models import RetrievalHit
from cite_or_die.retrieval.service import RetrievalService
from cite_or_die.service import CiteOrDieService


class TimedRetrieval(RetrievalService):
    def __init__(self) -> None:
        super().__init__(get_settings())
        self.elapsed_ms: list[float] = []

    @override
    async def retrieve(
        self,
        tenant_id: str,
        query: str,
        top_k: int,
        matter_id: str = "m_default",
        doc_ids: set[str] | None = None,
    ) -> list[RetrievalHit]:
        started = perf_counter()
        result = await super().retrieve(tenant_id, query, top_k, matter_id, doc_ids)
        self.elapsed_ms.append((perf_counter() - started) * 1000)
        return result


def main() -> None:
    retrieval = TimedRetrieval()
    service = CiteOrDieService(get_settings(), retrieval=retrieval)
    app.dependency_overrides[get_service] = lambda: service
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        async with original_lifespan(application):
            yield
        await asyncio.to_thread(
            Path(os.environ["PERFORMANCE_TIMINGS"]).write_text, json.dumps(retrieval.elapsed_ms)
        )

    app.router.lifespan_context = lifespan
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ["PERFORMANCE_PORT"]))


if __name__ == "__main__":
    main()
