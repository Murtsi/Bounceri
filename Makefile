SHELL := bash
.DEFAULT_GOAL := help

# --- project commands: set these once you pick a stack ------------------------
DEV_CMD   ?= echo "DEV_CMD not set - add your dev server command to the Makefile" && exit 1
TEST_CMD  ?= echo "TEST_CMD not set - add your test command to the Makefile" && exit 1
LINT_CMD  ?= echo "LINT_CMD not set - add your lint command to the Makefile" && exit 1
BUILD_CMD ?= echo "BUILD_CMD not set - add your build command to the Makefile" && exit 1
FMT_CMD   ?= echo "FMT_CMD not set - add your formatter command to the Makefile" && exit 1

-include .env
export

.PHONY: help setup hooks check dev test lint build fmt up down logs psql adminer reset-db clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create .env, init git, install hooks
	@bash scripts/setup.sh
	@bash scripts/install-hooks.sh

hooks: ## Install the pre-commit hook
	@bash scripts/install-hooks.sh

check: ## Repo hygiene checks (also run by pre-commit and CI)
	@bash scripts/check.sh
	@bash scripts/check-changelog.sh

dev: ## Start the dev server (edit DEV_CMD)
	@$(DEV_CMD)

test: ## Run tests (edit TEST_CMD)
	@$(TEST_CMD)

lint: ## Run linters (edit LINT_CMD)
	@$(LINT_CMD)

build: ## Build for production (edit BUILD_CMD)
	@$(BUILD_CMD)

fmt: ## Format the codebase (edit FMT_CMD)
	@$(FMT_CMD)

up: ## Start Postgres + Adminer
	@docker compose up -d --wait

down: ## Stop containers
	@docker compose down

logs: ## Follow container logs
	@docker compose logs -f --tail=100

psql: ## Open a psql shell in the db container
	@docker compose exec db psql -U "$${POSTGRES_USER:-junction}" -d "$${POSTGRES_DB:-junction}"

adminer: ## Print the Adminer URL
	@echo "Adminer: http://localhost:$${ADMINER_PORT:-8080}"

reset-db: ## Destroy and recreate the database volume
	@docker compose down -v
	@docker compose up -d --wait

clean: ## Remove common build artifacts
	@rm -rf node_modules .next dist build coverage .turbo .pytest_cache __pycache__ .ruff_cache .mypy_cache
