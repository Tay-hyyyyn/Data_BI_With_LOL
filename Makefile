.PHONY: api web test build up down health backup

api:
	uvicorn app.main:app --app-dir apps/backend --reload

web:
	cd apps/frontend && pnpm dev

test:
	pytest

build:
	cd apps/frontend && pnpm build

up:
	docker compose up --build -d

down:
	docker compose down

health:
	python scripts/healthcheck.py

backup:
	python scripts/backup_data.py
