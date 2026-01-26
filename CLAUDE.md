# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Timeplus Connector Registry is a FastAPI-based service that manages Custom Table Function (CTF) connectors for Timeplus. It provides a package manager for Timeplus data connectors, similar to npm/PyPI.

## Development Commands

### Docker Compose (Primary Development Method)
```bash
# Start all services (PostgreSQL, API, UI, and supporting services)
make start
# or: docker compose up

# View API logs
make logs
# or: docker-compose logs -f api

# Rebuild API container with fresh build
make build

# Stop all services
docker compose down

# Stop and remove data volumes
docker compose down -v
```

### Local Development (Alternative)
```bash
# Install in development mode
pip install -e .

# Run database migrations
alembic upgrade head

# Start development server
uvicorn registry.main:app --reload

# Run tests
pytest

# Code quality checks
black .                    # Format code
ruff check .              # Lint code
mypy registry/            # Type checking
```

### NATS Development Commands
The Makefile includes several NATS-related commands for testing connectors:
- `make nats-sub` / `make nats-pub` - Core NATS messaging
- `make nats-js-*` - JetStream commands (stream management, pub/sub)

## Architecture

### Core Structure
- **registry/main.py** - FastAPI application entry point with lifespan management
- **registry/routers/** - API route handlers (connectors, publishers, tags)
- **registry/services/** - Business logic layer
- **registry/models/** - SQLAlchemy ORM models
- **registry/schemas/** - Pydantic schemas for request/response validation
- **registry/utils/** - Utilities (auth, manifest parsing, SQL generation)

### Key Components
- **Connector Management** - YAML-based connector definitions in `samples/`
- **Publisher System** - Authentication and namespace management
- **SQL Generation** - Dynamic Timeplus SQL generation from connector specs
- **Database** - PostgreSQL with Alembic migrations

### Services Architecture
The application follows a layered architecture:
1. **Routers** (API layer) - Handle HTTP requests/responses
2. **Services** (Business logic) - Core application logic
3. **Models** (Data layer) - Database entity definitions

### Configuration
- Environment variables configured via `registry/config.py` using Pydantic settings
- Database URL, secret key, and debug mode are primary configuration points
- `.env.example` provides template for local development

### Authentication
- JWT-based authentication for publisher operations
- Public read access for connector browsing
- Publisher registration creates namespaces for connector publishing

## Testing

Tests are located in `tests/` directory with pytest configuration in `pyproject.toml`. The project uses:
- pytest for test framework
- pytest-asyncio for async test support
- pytest-cov for coverage reporting

## Docker Services

The docker-compose.yml includes:
- **postgres** - PostgreSQL 16 database
- **api** - FastAPI application
- **ui** - Nginx-served frontend
- **timeplus** - Timeplus database engine
- **redpanda** - Kafka-compatible streaming platform
- **nats/nats-js** - NATS messaging systems

## Code Quality

The project enforces code quality through:
- **Black** - Code formatting (line length: 100)
- **Ruff** - Linting and import sorting
- **MyPy** - Static type checking with strict mode
- **Python 3.11+** requirement