.PHONY: install test lint typecheck run smoke docker-up docker-down load

install:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy src/cite_or_die

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
