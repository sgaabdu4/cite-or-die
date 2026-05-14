#!/usr/bin/env bash
set -euo pipefail

repo_url="${CITE_OR_DIE_REPO_URL:-https://github.com/sgaabdu4/cite-or-die.git}"
install_dir="${CITE_OR_DIE_INSTALL_DIR:-cite-or-die}"

if [ ! -f pyproject.toml ] || [ ! -d src/cite_or_die ]; then
  command -v git >/dev/null 2>&1 || {
    echo "git is required when running install.sh outside a checkout"
    exit 1
  }
  if [ ! -d "$install_dir/.git" ]; then
    git clone "$repo_url" "$install_dir"
  fi
  cd "$install_dir"
fi

command -v uv >/dev/null 2>&1 || {
  echo "uv is required: https://docs.astral.sh/uv/"
  exit 1
}

python_bin="${PYTHON_BIN:-python3.11}"
command -v "$python_bin" >/dev/null 2>&1 || python_bin=python3

secret_hex() {
  "$python_bin" - <<'PY'
import secrets

print(secrets.token_hex(32))
PY
}

uv sync --extra dev
cp -n .env.example .env
mkdir -p data secrets "$HOME/.config/sops/age"

test -f secrets/auth_secret.txt || secret_hex > secrets/auth_secret.txt
test -f secrets/postgres_user.txt || printf 'cite_or_die\n' > secrets/postgres_user.txt
test -f secrets/postgres_password.txt || secret_hex > secrets/postgres_password.txt
test -f secrets/anthropic_api_key.txt || : > secrets/anthropic_api_key.txt
test -f secrets/openai_api_key.txt || : > secrets/openai_api_key.txt

if command -v age-keygen >/dev/null 2>&1 && [ ! -f "$HOME/.config/sops/age/keys.txt" ]; then
  age-keygen -o "$HOME/.config/sops/age/keys.txt" >/dev/null 2>&1
fi

echo "Installed. Run: uv run cite-or-die serve --host 127.0.0.1 --port 8765"
echo "Docker: docker compose up --build"
