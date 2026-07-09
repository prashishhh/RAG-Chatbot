.PHONY: dev db migrate test lint format clean help

dev: ## Start PostgreSQL + FastAPI (everyday use, no migrations)
	docker compose up -d
	@sleep 3
	.venv/bin/uvicorn app.main:app --reload

dev-fresh: ## First-time setup: PostgreSQL + migrations + FastAPI
	docker compose up -d
	@sleep 3
	.venv/bin/alembic upgrade head
	.venv/bin/uvicorn app.main:app --reload

db: ## Start PostgreSQL only
	docker compose up -d

db-stop: ## Stop PostgreSQL
	docker compose down

migrate: ## Run all pending Alembic migrations
	.venv/bin/alembic upgrade head

migrate-down: ## Rollback last migration
	.venv/bin/alembic downgrade -1

migrate-history: ## Show migration history
	.venv/bin/alembic history

test: ## Run all tests
	.venv/bin/pytest

test-v: ## Run all tests with verbose output
	.venv/bin/pytest -v

test-unit: ## Run only unit tests
	.venv/bin/pytest app/tests/unit/

test-integration: ## Run only integration tests
	.venv/bin/pytest app/tests/integration/

lint: ## Run Ruff linter
	.venv/bin/ruff check .

format: ## Auto-fix Ruff lint errors
	.venv/bin/ruff check . --fix

clean: ## Remove all __pycache__ and .pyc files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
