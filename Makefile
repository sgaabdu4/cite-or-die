.PHONY: setup install download-corpus download-tesla seed-tesla seed-all test lint typecheck eval eval-t2ragbench-100 e2e-local run smoke docker-up docker-down load

setup:
	uv sync --extra dev

install:
	uv sync --extra dev

download-corpus:
	uv run python scripts/download_corpus.py

download-tesla:
	uv run python scripts/download_corpus.py --tesla-only

seed-tesla: download-tesla
	uv run cite-or-die ingest examples/tesla_10k.html --tenant dev

seed-all: download-corpus
	uv run cite-or-die ingest examples/tesla_10k.html --tenant dev
	uv run cite-or-die ingest examples/uber_10k.html --tenant dev
	uv run cite-or-die ingest examples/snowflake_10k.pdf --tenant dev

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy src/cite_or_die app

eval:
	uv run pytest tests/eval -v

eval-t2ragbench-100:
	uv run pytest tests/eval/test_t2ragbench_gate.py -v

e2e-local: setup seed-tesla
	uv run pytest tests/unit tests/integration tests/eval -v

run:
	uv run cite-or-die serve --host 127.0.0.1 --port 8765

smoke:
	./scripts/smoke.sh

docker-up:
	docker compose up --build

docker-down:
	docker compose down --remove-orphans

load:
	uv run locust -f tests/load/locustfile.py --host http://127.0.0.1:8765
