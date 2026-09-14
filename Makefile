.PHONY: api web test build

api:
	uvicorn app.main:app --app-dir apps/backend --reload

web:
	cd apps/frontend && pnpm dev

test:
	pytest

build:
	cd apps/frontend && pnpm build
