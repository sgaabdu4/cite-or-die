#!/usr/bin/env bash
set -euo pipefail

tmp_dir="$(mktemp -d)"
export CITE_OR_DIE_APP_ENV=test
export CITE_OR_DIE_DATA_DIR="$tmp_dir"
export CITE_OR_DIE_AUTH_SECRET=smoke-secret

uv run python - <<'PY'
import asyncio

from cite_or_die.core.config import Settings
from cite_or_die.core.models import AuthContext, ChatRequest, Role
from cite_or_die.core.service import CiteOrDieService


async def main():
    service = CiteOrDieService(Settings())
    ctx = AuthContext(tenant_id="smoke", subject="smoke", roles=[Role.admin])
    await service.upload(ctx, "smoke.txt", "text/plain", b"Smoke tests verify cite-or-die locally.")
    response = await service.chat(ctx, ChatRequest(question="What do smoke tests verify?"))
    assert response.citations, response.model_dump()
    print(response.answer)


asyncio.run(main())
PY
