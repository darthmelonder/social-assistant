.PHONY: up down logs test test-backend test-frontend lint install frontend-install frontend-dev worker

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

install:
	cd backend && pip install -e ".[dev]"

frontend-install:
	cd frontend && npm install

test-backend:
	cd backend && pytest

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

lint:
	cd backend && ruff check app tests

frontend-dev:
	cd frontend && npm run dev

worker:
	cd backend && arq app.workers.arq_settings.WorkerSettings
