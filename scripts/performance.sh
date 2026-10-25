#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
reports="$root/coverage/performance"
work=$(mktemp -d "${TMPDIR:-/tmp}/cite-performance.XXXXXX")
server_pid=""
cleanup() {
  if [ -n "$server_pid" ] && kill -0 "$server_pid" 2>/dev/null; then
    kill -TERM "$server_pid"
    wait "$server_pid" || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$reports" "$work/main"
cd "$root"
git archive origin/main | tar -x -C "$work/main"
cp tests/performance/retrieval_benchmark.py "$work/main/retrieval_benchmark.py"
(
  cd "$work/main"
  unset VIRTUAL_ENV
  uv sync --locked --extra dev
  uv run --no-sync pytest retrieval_benchmark.py --benchmark-only --benchmark-json="$reports/main.json"
)
uv run --no-sync pytest tests/performance/retrieval_benchmark.py --benchmark-only --benchmark-json="$reports/current.json"

export PERFORMANCE_PORT
PERFORMANCE_PORT=$(uv run --no-sync python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
export PERFORMANCE_TIMINGS="$reports/retrieval-ms.json"
export CITE_OR_DIE_APP_ENV=test CITE_OR_DIE_DATA_DIR="$work/data"
export CITE_OR_DIE_VECTOR_BACKEND=memory CITE_OR_DIE_EMBEDDING_PROVIDER=hash
export CITE_OR_DIE_LLM_PROVIDER=fake CITE_OR_DIE_RERANKER_PROVIDER=lexical
.venv/bin/python -m tests.load.server > "$reports/server.log" 2>&1 &
server_pid=$!
url="http://127.0.0.1:$PERFORMANCE_PORT"
deadline=$((SECONDS + 60))
until curl --silent --fail --max-time 1 "$url/readyz" >/dev/null; do
  kill -0 "$server_pid"
  if ((SECONDS >= deadline)); then
    cat "$reports/server.log"
    exit 1
  fi
  sleep 0.1
done
uv run --no-sync locust -f tests/load/locustfile.py --host "$url" --headless \
  --users 10 --spawn-rate 10 --run-time 60s --stop-timeout 10 \
  --csv "$reports/load" --only-summary
kill -TERM "$server_pid"
wait "$server_pid" || test "$?" -eq 143
server_pid=""
uv run --no-sync pytest tests/performance/performance_checks.py --junitxml=coverage/performance.xml -s
