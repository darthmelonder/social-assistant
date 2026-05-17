.PHONY: up down logs test test-backend test-frontend lint install frontend-install frontend-dev worker

# Path to the project-level virtual environment binaries
VENV := .venv/bin

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

install:
	python3 -m venv .venv
	$(VENV)/pip install -e "backend[dev]"

frontend-install:
	cd frontend && npm install

test-backend:
	cd backend && ../$(VENV)/pytest

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

lint:
	cd backend && ../$(VENV)/ruff check app tests

frontend-dev:
	cd frontend && npm run dev

worker:
	cd backend && ../$(VENV)/arq app.workers.arq_settings.WorkerSettings
