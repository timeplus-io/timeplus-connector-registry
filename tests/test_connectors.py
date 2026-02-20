"""Tests for connector service and API."""

import pytest
from httpx import ASGITransport, AsyncClient

from registry.main import app
from registry.database import init_db, close_db
from registry.utils import parse_manifest, generate_install_sql


# Sample manifest for testing
SAMPLE_MANIFEST = """
apiVersion: v1
kind: Connector

metadata:
  name: test-connector
  namespace: testpub
  version: 1.0.0
  displayName: Test Connector
  description: A test connector
  license: MIT

spec:
  category: source
  mode: streaming
  
  tags:
    - test
    - example
  
  dependencies:
    - requests>=2.28.0
  
  schema:
    columns:
      - name: value
        type: int32
        description: Test value

  functions:
    read:
      name: test_read
      description: Test read function

  pythonCode: |
    def test_read():
        for i in range(10):
            yield [i]

  examples:
    - title: Basic usage
      code: SELECT * FROM test_connector;
"""


class TestManifestParsing:
    """Test manifest parsing utilities."""

    def test_parse_valid_manifest(self):
        """Test parsing a valid manifest."""
        manifest = parse_manifest(SAMPLE_MANIFEST)
        
        assert manifest.metadata.name == "test-connector"
        assert manifest.metadata.namespace == "testpub"
        assert manifest.metadata.version == "1.0.0"
        assert manifest.spec.category.value == "source"
        assert manifest.spec.mode.value == "streaming"
        assert len(manifest.spec.schema_.columns) == 1
        assert manifest.spec.functions.read is not None
        assert manifest.spec.functions.write is None

    def test_parse_invalid_yaml(self):
        """Test parsing invalid YAML."""
        from registry.utils import ManifestError
        
        with pytest.raises(ManifestError) as exc_info:
            parse_manifest("invalid: yaml: content:")
        
        assert "Invalid YAML" in str(exc_info.value)

    def test_parse_missing_required_fields(self):
        """Test parsing manifest with missing required fields."""
        from registry.utils import ManifestError
        
        invalid_manifest = """
apiVersion: v1
kind: Connector
metadata:
  name: test
"""
        with pytest.raises(ManifestError) as exc_info:
            parse_manifest(invalid_manifest)
        
        assert "validation failed" in str(exc_info.value.message).lower()


class TestSQLGeneration:
    """Test SQL generation utilities."""

    def test_generate_source_sql(self):
        """Test SQL generation for source connector."""
        manifest = {
            "metadata": {
                "namespace": "testpub",
                "name": "test-source",
                "version": "1.0.0",
            },
            "spec": {
                "category": "source",
                "mode": "streaming",
                "dependencies": ["requests>=2.28.0"],
                "schema": {
                    "columns": [
                        {"name": "value", "type": "int32"}
                    ]
                },
                "functions": {
                    "read": {"name": "test_read"}
                },
                "pythonCode": "def test_read():\n    yield [1]",
            }
        }
        
        sql = generate_install_sql(manifest)
        
        assert "CREATE EXTERNAL STREAM test_source" in sql
        assert "value int32" in sql
        assert "read_function_name='test_read'" in sql
        assert "SYSTEM INSTALL PYTHON PACKAGE 'requests>=2.28.0'" in sql
        assert "SELECT * FROM test_source" in sql

    def test_generate_sink_sql(self):
        """Test SQL generation for sink connector."""
        manifest = {
            "metadata": {
                "namespace": "testpub",
                "name": "test-sink",
                "version": "1.0.0",
            },
            "spec": {
                "category": "sink",
                "mode": "streaming",
                "dependencies": [],
                "schema": {
                    "columns": [
                        {"name": "message", "type": "string"}
                    ]
                },
                "functions": {
                    "write": {"name": "test_sink"}
                },
                "pythonCode": "def test_sink(values):\n    pass",
            }
        }
        
        sql = generate_install_sql(manifest)
        
        assert "CREATE EXTERNAL STREAM test_sink" in sql
        assert "write_function_name='test_sink'" in sql
        assert "INSERT INTO test_sink" in sql

    def test_custom_stream_name(self):
        """Test SQL generation with custom stream name."""
        manifest = {
            "metadata": {
                "namespace": "testpub",
                "name": "test-connector",
                "version": "1.0.0",
            },
            "spec": {
                "category": "source",
                "mode": "streaming",
                "dependencies": [],
                "schema": {"columns": [{"name": "v", "type": "int32"}]},
                "functions": {"read": {"name": "read_fn"}},
                "pythonCode": "def read_fn(): yield [1]",
            }
        }
        
        sql = generate_install_sql(manifest, stream_name="my_custom_stream")
        
        assert "CREATE EXTERNAL STREAM my_custom_stream" in sql


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Initialize database for tests."""
    await init_db()
    yield
    await close_db()


@pytest.fixture
async def client():
    """Get async client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
class TestConnectorAPI:
    """Test connector API endpoints."""

    async def test_health_check(self, client):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_list_connectors_empty(self, client):
        """Test listing connectors when empty."""
        response = await client.get("/api/v1/connectors")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data

    async def test_connector_not_found(self, client):
        """Test getting non-existent connector."""
        response = await client.get("/api/v1/connectors/nonexistent/connector")
        assert response.status_code == 404

    async def test_publish_requires_auth(self, client):
        """Test that publishing requires authentication."""
        response = await client.post(
            "/api/v1/connectors",
            content=SAMPLE_MANIFEST,
            headers={"Content-Type": "application/x-yaml"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestPublisherAPI:
    """Test publisher API endpoints."""

    async def test_register_publisher(self, client):
        """Test publisher registration."""
        response = await client.post(
            "/api/v1/register",
            json={
                "namespace": "testpub",
                "display_name": "Test Publisher",
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )
        # Note: This should pass now with SQLite database correctly initialized
        assert response.status_code == 201

    async def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/v1/login",
            json={
                "namespace": "nonexistent",
                "password": "wrongpassword",
            },
        )
        # Should be 401 (unauthorized)
        assert response.status_code == 401
