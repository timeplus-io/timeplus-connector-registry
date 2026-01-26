# Timeplus Connector Registry Makefile
# =====================================

.PHONY: help install dev test lint format typecheck clean \
        start stop restart build logs shell db-migrate db-shell \
        nats-sub nats-pub nats-js-sub nats-js-pub \
        nats-js-stream-create nats-js-stream-list nats-js-stream-info \
        nats-js-stream-delete nats-js-stream-pub nats-js-stream-sub

.DEFAULT_GOAL := help

# Colors for terminal output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# Configuration
COMPOSE := docker compose
API_CONTAINER := registry-api
POSTGRES_CONTAINER := registry-postgres
NATS_HOST := host.docker.internal
NATS_PORT := 4222
NATS_JS_PORT := 4223

#------------------------------------------------------------------------------
# Help
#------------------------------------------------------------------------------

help: ## Show this help message
	@echo "$(GREEN)Timeplus Connector Registry$(NC)"
	@echo "============================"
	@echo ""
	@echo "$(BLUE)Usage:$(NC) make [target]"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} \
		/^[a-zA-Z_-]+:.*##/ { printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2 } \
		/^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ Development - Local

install: ## Install package in development mode with dev dependencies
	pip install -e ".[dev]"

dev: ## Run development server locally (requires local postgres)
	uvicorn registry.main:app --reload --host 0.0.0.0 --port 8000

run: ## Run server locally (production mode)
	uvicorn registry.main:app --host 0.0.0.0 --port 8000

##@ Development - Docker

start: ## Start all services with Docker Compose
	$(COMPOSE) up

start-d: ## Start all services in detached mode
	$(COMPOSE) up -d

stop: ## Stop all services
	$(COMPOSE) down

restart: ## Restart all services
	$(COMPOSE) down && $(COMPOSE) up -d

build: ## Rebuild API container (clean build)
	$(COMPOSE) down
	docker rmi registry-api --force 2>/dev/null || true
	docker builder prune -f
	$(COMPOSE) build --no-cache

build-quick: ## Quick rebuild API container (with cache)
	$(COMPOSE) build api

logs: ## Follow API logs
	$(COMPOSE) logs -f api

logs-all: ## Follow all service logs
	$(COMPOSE) logs -f

shell: ## Open shell in API container
	docker exec -it $(API_CONTAINER) /bin/sh

clean: ## Stop services and remove volumes
	$(COMPOSE) down -v
	docker rmi registry-api --force 2>/dev/null || true

ps: ## Show running containers
	$(COMPOSE) ps

##@ Testing

test: ## Run tests
	pytest

test-v: ## Run tests with verbose output
	pytest -v

test-cov: ## Run tests with coverage report
	pytest --cov=registry --cov-report=term-missing

test-cov-html: ## Run tests with HTML coverage report
	pytest --cov=registry --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

##@ Code Quality

format: ## Format code with black
	black .

lint: ## Lint code with ruff
	ruff check .

lint-fix: ## Lint and auto-fix code with ruff
	ruff check . --fix

typecheck: ## Run type checking with mypy
	mypy registry/

check: lint typecheck ## Run all code quality checks (lint + typecheck)

ci: format lint typecheck test ## Run full CI pipeline (format, lint, typecheck, test)

##@ Database

db-migrate: ## Run database migrations
	alembic upgrade head

db-downgrade: ## Rollback last migration
	alembic downgrade -1

db-history: ## Show migration history
	alembic history

db-shell: ## Open PostgreSQL shell
	docker exec -it $(POSTGRES_CONTAINER) psql -U postgres -d registry

db-reset: ## Reset database (drop and recreate)
	docker exec -it $(POSTGRES_CONTAINER) psql -U postgres -c "DROP DATABASE IF EXISTS registry;"
	docker exec -it $(POSTGRES_CONTAINER) psql -U postgres -c "CREATE DATABASE registry;"
	$(COMPOSE) exec api alembic upgrade head

##@ NATS - Core

nats-sub: ## Subscribe to NATS topic (core)
	docker run -it --rm natsio/nats-box nats sub -s nats://$(NATS_HOST):$(NATS_PORT) test_topic

nats-pub: ## Publish to NATS topic (core)
	docker run -it --rm natsio/nats-box nats pub -s nats://$(NATS_HOST):$(NATS_PORT) test_topic "test message"

##@ NATS - JetStream

nats-js-sub: ## Subscribe to JetStream topic
	docker run -it --rm natsio/nats-box nats sub -s nats://$(NATS_HOST):$(NATS_JS_PORT) test_topic

nats-js-pub: ## Publish to JetStream topic
	docker run -it --rm natsio/nats-box nats pub -s nats://$(NATS_HOST):$(NATS_JS_PORT) test_topic "test message"

nats-js-stream-create: ## Create JetStream stream (EVENTS)
	docker run --rm natsio/nats-box nats stream add EVENTS \
		--subjects "events.>" \
		--storage file \
		--retention limits \
		--discard old \
		--max-msgs=-1 \
		--max-bytes=-1 \
		--max-age=1y \
		--max-msg-size=-1 \
		--max-msgs-per-subject=-1 \
		--max-consumers=-1 \
		--replicas=1 \
		--defaults \
		--server nats://$(NATS_HOST):$(NATS_JS_PORT)

nats-js-stream-list: ## List JetStream streams
	docker run --rm natsio/nats-box nats stream list --server nats://$(NATS_HOST):$(NATS_JS_PORT)

nats-js-stream-info: ## Get JetStream stream info (EVENTS)
	docker run --rm natsio/nats-box nats stream info EVENTS --server nats://$(NATS_HOST):$(NATS_JS_PORT)

nats-js-stream-delete: ## Delete JetStream stream (EVENTS)
	docker run --rm natsio/nats-box nats stream delete EVENTS --force --server nats://$(NATS_HOST):$(NATS_JS_PORT)

nats-js-stream-pub: ## Publish to JetStream stream
	docker run --rm natsio/nats-box nats pub events.data "Test message from JetStream" --server nats://$(NATS_HOST):$(NATS_JS_PORT)

nats-js-stream-sub: ## Subscribe to JetStream stream
	docker run --rm -it natsio/nats-box nats sub "events.>" --server nats://$(NATS_HOST):$(NATS_JS_PORT)

##@ Kafka/Redpanda

kafka-topics: ## List Kafka topics
	docker exec -it $$(docker ps -qf "name=redpanda") rpk topic list

kafka-create-topic: ## Create Kafka topic (usage: make kafka-create-topic TOPIC=my-topic)
	docker exec -it $$(docker ps -qf "name=redpanda") rpk topic create $(TOPIC)

kafka-consume: ## Consume from Kafka topic (usage: make kafka-consume TOPIC=my-topic)
	docker exec -it $$(docker ps -qf "name=redpanda") rpk topic consume $(TOPIC)

kafka-produce: ## Produce to Kafka topic (usage: make kafka-produce TOPIC=my-topic)
	docker exec -it $$(docker ps -qf "name=redpanda") rpk topic produce $(TOPIC)
