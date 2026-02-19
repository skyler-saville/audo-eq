SHELL := /bin/bash

.DEFAULT_GOAL := help

ENV_FILE ?= .env
POETRY ?= poetry
UVICORN_APP ?= audo_eq.api:app
PORT_CHECK ?= ./scripts/check_ports.py

# Load local env if present so Make targets share the same config as Compose/app scripts.
ifneq (,$(wildcard $(ENV_FILE)))
include $(ENV_FILE)
export
endif

API_HOST ?= 0.0.0.0
API_PORT ?= 8000
AUDO_EQ_API_BASE_URL ?= http://127.0.0.1:$(API_PORT)
AUDO_EQ_FRONTEND_HOST ?= 0.0.0.0
AUDO_EQ_FRONTEND_PORT ?= 5000

COMPOSE_BASE := docker compose --env-file $(ENV_FILE)
COMPOSE_DEV_FILES := -f compose.yaml -f compose.override.yaml
COMPOSE_PROD_FILES := -f compose.yaml -f compose.prod.yaml

.PHONY: help ensure-env install test api frontend preflight-dev preflight-prod dev-up dev-down prod-up prod-down logs health

help: ## Show available commands.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ { printf "  %-16s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

ensure-env: ## Create .env from .env.example if missing.
	@if [[ ! -f "$(ENV_FILE)" ]]; then \
		cp .env.example $(ENV_FILE); \
		echo "Created $(ENV_FILE) from .env.example"; \
	else \
		echo "$(ENV_FILE) already exists"; \
	fi

install: ## Install dependencies with Poetry.
	$(POETRY) install

test: ## Run unit tests.
	$(POETRY) run pytest

api: ## Run FastAPI locally with hot reload.
	$(POETRY) run uvicorn $(UVICORN_APP) --host $(API_HOST) --port $(API_PORT) --reload

frontend: ## Run Flask frontend with API URL from .env/.make vars.
	AUDO_EQ_API_BASE_URL=$(AUDO_EQ_API_BASE_URL) \
	AUDO_EQ_FRONTEND_HOST=$(AUDO_EQ_FRONTEND_HOST) \
	AUDO_EQ_FRONTEND_PORT=$(AUDO_EQ_FRONTEND_PORT) \
	$(POETRY) run audo-eq-frontend

preflight-dev: ensure-env ## Check dev compose host ports for collisions.
	$(PORT_CHECK) --env-file $(ENV_FILE) --mode dev

preflight-prod: ensure-env ## Check prod compose host ports for collisions.
	$(PORT_CHECK) --env-file $(ENV_FILE) --mode prod

dev-up: preflight-dev ## Start Docker Compose in local development mode.
	$(COMPOSE_BASE) $(COMPOSE_DEV_FILES) up --build

dev-down: ensure-env ## Stop Docker Compose development stack.
	$(COMPOSE_BASE) $(COMPOSE_DEV_FILES) down

prod-up: preflight-prod ## Start Docker Compose in production-style mode.
	$(COMPOSE_BASE) $(COMPOSE_PROD_FILES) up -d --build

prod-down: ensure-env ## Stop Docker Compose production-style stack.
	$(COMPOSE_BASE) $(COMPOSE_PROD_FILES) down

logs: ensure-env ## Tail API logs from the development stack.
	$(COMPOSE_BASE) $(COMPOSE_DEV_FILES) logs -f api

health: ## Check local API health endpoint.
	curl --fail --silent --show-error http://127.0.0.1:$(API_PORT)/health
