.PHONY: api web test build lint typecheck gate types

api:
	uvicorn app.main:app --app-dir apps/backend --reload

web:
	cd apps/frontend && pnpm dev

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy

# Everything CI runs for the backend. Run before pushing.
gate: lint typecheck test

types:
	python scripts/gen_openapi.py

build:
	cd apps/frontend && pnpm build
