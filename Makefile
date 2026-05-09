.PHONY: up down logs test lint install

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

install:
	cd backend && pip install -e ".[dev]"

test:
	cd backend && pytest

lint:
	cd backend && ruff check app tests
