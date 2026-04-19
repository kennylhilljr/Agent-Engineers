.DEFAULT_GOAL := help

.PHONY: help install dev test lint format typecheck security-audit clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	uv pip install -r requirements.txt

dev: ## Install dev dependencies and pre-commit hooks
	uv pip install -r requirements.txt
	uv pip install -r requirements-dev.txt
	uv pip install pre-commit
	pre-commit install

test: ## Run test suite
	uv run python -m pytest tests/ -v

lint: ## Run ruff linter
	uv run ruff check .

format: ## Run ruff formatter
	uv run ruff format .

typecheck: ## Run mypy type checking
	uv run mypy agent.py client.py security.py progress.py prompts.py \
		agents/ tenants/ memory/ specs/ daemon/ bridges/ --ignore-missing-imports

security-audit: ## Run security hook tests
	uv run python scripts/test_security.py

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage coverage.xml
