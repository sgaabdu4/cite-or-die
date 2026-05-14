from __future__ import annotations

import argparse
import asyncio
import os
import tempfile
from pathlib import Path
from typing import Literal, cast

import httpx
from pydantic import SecretStr

from cite_or_die.core.config import Settings
from cite_or_die.core.models import AuthContext, ChatRequest, Role
from cite_or_die.core.service import CiteOrDieService


def _secret_from_env(name: str) -> SecretStr:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is required for this provider smoke test")
    return SecretStr(value)


async def _ollama_model(base_url: str) -> str:
    configured = os.environ.get("CITE_OR_DIE_LLM_MODEL")
    if configured:
        return configured
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{base_url.rstrip('/')}/api/tags")
    response.raise_for_status()
    models = response.json().get("models", [])
    if not models:
        raise SystemExit("Ollama has no local models; run `ollama pull <model>` first")
    return str(models[0]["name"])


async def _settings(provider: str, data_dir: Path) -> Settings:
    llm_provider = cast(Literal["fake", "anthropic", "openai", "ollama"], provider)
    model = os.environ.get("CITE_OR_DIE_LLM_MODEL", "fake-deterministic-v1")
    anthropic_key: SecretStr | None = None
    openai_key: SecretStr | None = None
    ollama_base_url = os.environ.get("CITE_OR_DIE_OLLAMA_BASE_URL", "http://localhost:11434")

    if provider == "anthropic":
        anthropic_key = _secret_from_env("CITE_OR_DIE_ANTHROPIC_API_KEY")
        if model == "fake-deterministic-v1":
            raise SystemExit("CITE_OR_DIE_LLM_MODEL must name an Anthropic model")
    if provider == "openai":
        openai_key = _secret_from_env("CITE_OR_DIE_OPENAI_API_KEY")
        if model == "fake-deterministic-v1":
            raise SystemExit("CITE_OR_DIE_LLM_MODEL must name an OpenAI model")
    if provider == "ollama":
        model = await _ollama_model(ollama_base_url)

    return Settings(
        app_env="test",
        data_dir=data_dir,
        auth_secret=SecretStr("provider-smoke-secret-with-at-least-32-bytes"),
        vector_backend="memory",
        embedding_provider="hash",
        llm_provider=llm_provider,
        llm_model=model,
        anthropic_api_key=anthropic_key,
        openai_api_key=openai_key,
        ollama_base_url=ollama_base_url,
    )


async def _run(provider: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        settings = await _settings(provider, Path(tmp))
        service = CiteOrDieService(settings)
        ctx = AuthContext(tenant_id="provider-smoke", subject="smoke", roles=[Role.admin])
        await service.upload(
            ctx,
            "provider-smoke.txt",
            "text/plain",
            b"Provider smoke says cite-or-die sends only retrieved chunks.",
        )
        response = await service.chat(
            ctx,
            ChatRequest(question="What does provider smoke say?", top_k=3),
        )
        if not response.citations:
            raise SystemExit(response.model_dump_json(indent=2))
        print(f"{provider}: {response.model_provider}/{response.model_version} ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "provider",
        choices=["fake", "anthropic", "openai", "ollama"],
        help="Provider to exercise through the service /chat path.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.provider))


if __name__ == "__main__":
    main()
