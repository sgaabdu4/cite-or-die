#!/usr/bin/env bash
set -euo pipefail

command -v uv >/dev/null 2>&1 || {
  echo "uv is required: https://docs.astral.sh/uv/"
  exit 1
}

uv sync --extra dev
cp -n .env.example .env
mkdir -p data secrets
test -f secrets/auth_secret.txt || openssl rand -hex 32 > secrets/auth_secret.txt
echo "Installed. Run: uv run cite-or-die serve --host 127.0.0.1 --port 8765"
