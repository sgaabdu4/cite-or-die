.PHONY: setup install download-corpus download-tesla download-t2ragbench-subset seed-tesla seed-all test lint typecheck eval eval-t2ragbench-100 e2e-multitenant e2e-local run smoke provider-smoke provider-smoke-all gen-adversarial adversarial mutation docker-up docker-down load

setup:
	uv sync --extra dev

install:
	./install.sh

download-corpus:
	uv run python scripts/download_corpus.py

download-tesla:
	uv run python scripts/download_corpus.py --tesla-only

download-t2ragbench-subset:
	uv run python scripts/download_t2ragbench_subset.py

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

e2e-multitenant:
	uv run pytest tests/integration/test_phase2_walls.py -v

e2e-local: setup seed-tesla
	uv run pytest tests/unit tests/integration tests/eval -v

run:
	uv run cite-or-die serve --host 127.0.0.1 --port 8765

smoke:
	./scripts/smoke.sh

provider-smoke:
	uv run python scripts/provider_smoke.py $${PROVIDER:-fake}

provider-smoke-all:
	uv run python scripts/provider_smoke.py anthropic
	uv run python scripts/provider_smoke.py openai
	uv run python scripts/provider_smoke.py ollama

gen-adversarial:
	uv run python tests/adversarial/gen_adversarial_pdfs.py

adversarial: gen-adversarial
	uv run pytest tests/adversarial -v
	uv run python scripts/run_adversarial_probes.py --suite all

mutation:
	uv run python scripts/mutation_gate.py --threshold 0.70

docker-up:
	docker compose up --build

docker-down:
	docker compose down --remove-orphans

load:
	uv run locust -f tests/load/locustfile.py --host http://127.0.0.1:8765
