# Repository Guidelines

## Project Structure & Module Organization
Core application code lives in `registry/`:
- `main.py` (FastAPI app entry), `config.py`, `database.py`
- `routers/` for API endpoints, `services/` for business logic
- `models/` (SQLAlchemy), `schemas/` (Pydantic), `utils/` helpers
- `static/index.html` serves the embedded UI

Tests are in `tests/` (`conftest.py` shared fixtures, `test_*.py` test modules). Database migrations are under `alembic/versions/`. Example connector manifests and SQL are in `samples/`. Runtime config lives in `.env` (copy from `.env.example`).

## Build, Test, and Development Commands
Use the `Makefile` as the primary entrypoint:
- `make install` - install package with dev dependencies.
- `make dev` - run local API with reload on `:8000`.
- `make start-d` / `make stop` - start/stop Docker Compose stack.
- `make test` / `make test-cov` - run pytest (optionally with coverage).
- `make lint` / `make typecheck` / `make check` - Ruff + MyPy validation.
- `make db-migrate` - apply Alembic migrations.

For quick local run without Make: `uvicorn registry.main:app --reload`.

## Coding Style & Naming Conventions
Target Python `>=3.11` (CI uses 3.12). Follow Black + Ruff + strict MyPy:
- Format: `black .` (line length 100)
- Lint: `ruff check .`
- Types: `mypy registry/`

Use `snake_case` for functions/variables/modules, `PascalCase` for classes, and explicit type hints on non-trivial logic.

## Testing Guidelines
Framework: `pytest` with `pytest-asyncio` (`asyncio_mode=auto`).
- Name files `tests/test_*.py` and test functions `test_*`.
- Prefer API tests using `httpx.AsyncClient` fixture from `tests/conftest.py`.
- Cover manifest parsing, SQL generation, auth boundaries, and error paths for new features.

Run `make test-cov` before opening a PR.

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit subjects (for example: `add docker build`, `move postgres to sqlite`, `update release version`). Keep commits focused and reviewable.

PRs should include:
- Clear summary of behavior changes and affected modules
- Linked issue/context when relevant
- Test evidence (`make test`, `make check` output)
- Sample payload/response snippets for API changes

Ensure CI (`pytest`, Ruff, MyPy) is green before merge.
