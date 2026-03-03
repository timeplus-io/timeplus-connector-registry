"""Shared pytest fixtures and test environment setup."""

import os
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

TEST_DB_PATH = Path("/tmp") / f"timeplus_connector_registry_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DEBUG"] = "true"

from registry.database import close_db, init_db  # noqa: E402
from registry.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Initialize and cleanup the test database once per test session."""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    await init_db()
    yield
    await close_db()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
async def client():
    """Get async client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client
