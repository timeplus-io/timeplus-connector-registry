"""Tests for connector service and API."""

import asyncio

import pytest

import registry.main as main_module
from registry.utils import create_access_token, generate_install_sql, parse_manifest

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

    def test_generate_sql_with_conflicting_dollar_quote_tokens(self):
        """Should pick a non-conflicting dollar quote tag instead of failing."""
        manifest = {
            "metadata": {
                "namespace": "testpub",
                "name": "dollar-tag-conflict",
                "version": "1.0.0",
            },
            "spec": {
                "category": "source",
                "mode": "streaming",
                "dependencies": [],
                "schema": {"columns": [{"name": "v", "type": "int32"}]},
                "functions": {"read": {"name": "read_fn"}},
                "pythonCode": (
                    "def read_fn():\n"
                    "    marker = '$tp$ $ctf$ $pycode$'\n"
                    "    yield [1]\n"
                ),
            },
        }

        sql = generate_install_sql(manifest)

        assert "AS $tp1$" in sql
        assert "$tp1$\nSETTINGS" in sql


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

    async def test_sql_download_count_not_incremented_on_invalid_stream_name(self, client):
        """Failed SQL generation should not be counted as a successful download."""
        namespace = "dlpub"
        manifest = SAMPLE_MANIFEST.replace("namespace: testpub", f"namespace: {namespace}", 1)

        register = await client.post(
            "/api/v1/register",
            json={
                "namespace": namespace,
                "display_name": "Download Test Publisher",
                "email": "download-test@example.com",
                "password": "securepassword123",
            },
        )
        assert register.status_code == 201
        token = register.json()["access_token"]

        publish = await client.post(
            "/api/v1/connectors",
            content=manifest,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-yaml",
            },
        )
        assert publish.status_code == 201

        invalid_sql = await client.get(
            f"/api/v1/connectors/{namespace}/test-connector/sql?name=invalid-name"
        )
        assert invalid_sql.status_code == 400

        detail_after_failed = await client.get(f"/api/v1/connectors/{namespace}/test-connector")
        assert detail_after_failed.status_code == 200
        assert detail_after_failed.json()["downloads"] == 0


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


@pytest.mark.asyncio
class TestRateLimitMiddleware:
    """Test in-memory rate limit behavior and keying."""

    async def test_fake_bearer_token_uses_anonymous_limit(self, client):
        """Invalid bearer tokens should not use authenticated quota."""
        original_anon = main_module.settings.rate_limit_anonymous
        original_auth = main_module.settings.rate_limit_authenticated
        original_window = main_module.settings.rate_limit_window_seconds
        main_module._rate_limit_events.clear()
        try:
            main_module.settings.rate_limit_anonymous = 1
            main_module.settings.rate_limit_authenticated = 100
            main_module.settings.rate_limit_window_seconds = 60

            headers = {"Authorization": "Bearer this-is-not-a-valid-jwt"}
            first = await client.get("/api/v1/connectors", headers=headers)
            second = await client.get("/api/v1/connectors", headers=headers)

            assert first.status_code == 200
            assert first.headers["X-RateLimit-Limit"] == "1"
            assert second.status_code == 429
        finally:
            main_module.settings.rate_limit_anonymous = original_anon
            main_module.settings.rate_limit_authenticated = original_auth
            main_module.settings.rate_limit_window_seconds = original_window
            main_module._rate_limit_events.clear()

    async def test_stale_rate_limit_buckets_are_pruned(self, client):
        """Expired per-client buckets should be removed to avoid unbounded growth."""
        original_anon = main_module.settings.rate_limit_anonymous
        original_auth = main_module.settings.rate_limit_authenticated
        original_window = main_module.settings.rate_limit_window_seconds
        original_use_forwarded = main_module.settings.rate_limit_use_forwarded_for
        main_module._rate_limit_events.clear()
        try:
            main_module.settings.rate_limit_anonymous = 100
            main_module.settings.rate_limit_authenticated = 100
            main_module.settings.rate_limit_window_seconds = 1
            main_module.settings.rate_limit_use_forwarded_for = False

            for index in range(10):
                token = create_access_token({"sub": f"publisher-{index}"})
                response = await client.get(
                    "/api/v1/connectors",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 200

            assert len(main_module._rate_limit_events) == 10

            await asyncio.sleep(1.1)
            active_token = create_access_token({"sub": "active-publisher"})
            response = await client.get(
                "/api/v1/connectors",
                headers={"Authorization": f"Bearer {active_token}"},
            )
            assert response.status_code == 200

            assert list(main_module._rate_limit_events.keys()) == ["auth:active-publisher"]
        finally:
            main_module.settings.rate_limit_anonymous = original_anon
            main_module.settings.rate_limit_authenticated = original_auth
            main_module.settings.rate_limit_window_seconds = original_window
            main_module.settings.rate_limit_use_forwarded_for = original_use_forwarded
            main_module._rate_limit_events.clear()

    async def test_anonymous_limit_uses_forwarded_ip_when_enabled(self, client):
        """When enabled, forwarded client IP should define anonymous limit key."""
        original_anon = main_module.settings.rate_limit_anonymous
        original_auth = main_module.settings.rate_limit_authenticated
        original_window = main_module.settings.rate_limit_window_seconds
        original_use_forwarded = main_module.settings.rate_limit_use_forwarded_for
        main_module._rate_limit_events.clear()
        try:
            main_module.settings.rate_limit_anonymous = 1
            main_module.settings.rate_limit_authenticated = 100
            main_module.settings.rate_limit_window_seconds = 60
            main_module.settings.rate_limit_use_forwarded_for = True

            client_a = {"X-Forwarded-For": "203.0.113.10"}
            client_b = {"X-Forwarded-For": "203.0.113.11"}

            first_a = await client.get("/api/v1/connectors", headers=client_a)
            first_b = await client.get("/api/v1/connectors", headers=client_b)
            second_a = await client.get("/api/v1/connectors", headers=client_a)

            assert first_a.status_code == 200
            assert first_b.status_code == 200
            assert second_a.status_code == 429
        finally:
            main_module.settings.rate_limit_anonymous = original_anon
            main_module.settings.rate_limit_authenticated = original_auth
            main_module.settings.rate_limit_window_seconds = original_window
            main_module.settings.rate_limit_use_forwarded_for = original_use_forwarded
            main_module._rate_limit_events.clear()

    async def test_rate_limited_response_includes_cors_headers(self, client):
        """Rate-limited API responses should retain CORS accessibility for browsers."""
        original_anon = main_module.settings.rate_limit_anonymous
        original_auth = main_module.settings.rate_limit_authenticated
        original_window = main_module.settings.rate_limit_window_seconds
        original_use_forwarded = main_module.settings.rate_limit_use_forwarded_for
        main_module._rate_limit_events.clear()
        try:
            main_module.settings.rate_limit_anonymous = 1
            main_module.settings.rate_limit_authenticated = 100
            main_module.settings.rate_limit_window_seconds = 60
            main_module.settings.rate_limit_use_forwarded_for = False

            origin = "http://localhost:8000"
            first = await client.get("/api/v1/connectors", headers={"Origin": origin})
            second = await client.get("/api/v1/connectors", headers={"Origin": origin})

            assert first.status_code == 200
            assert second.status_code == 429
            assert second.headers.get("access-control-allow-origin") == origin
        finally:
            main_module.settings.rate_limit_anonymous = original_anon
            main_module.settings.rate_limit_authenticated = original_auth
            main_module.settings.rate_limit_window_seconds = original_window
            main_module.settings.rate_limit_use_forwarded_for = original_use_forwarded
            main_module._rate_limit_events.clear()

    async def test_non_positive_limit_returns_429_instead_of_500(self, client):
        """Misconfigured limits should not crash middleware with IndexError."""
        original_anon = main_module.settings.rate_limit_anonymous
        original_auth = main_module.settings.rate_limit_authenticated
        original_window = main_module.settings.rate_limit_window_seconds
        original_use_forwarded = main_module.settings.rate_limit_use_forwarded_for
        main_module._rate_limit_events.clear()
        try:
            main_module.settings.rate_limit_anonymous = 0
            main_module.settings.rate_limit_authenticated = 100
            main_module.settings.rate_limit_window_seconds = 60
            main_module.settings.rate_limit_use_forwarded_for = False

            response = await client.get("/api/v1/connectors")
            assert response.status_code == 429
            assert response.json()["error"] == "rate_limit_exceeded"
        finally:
            main_module.settings.rate_limit_anonymous = original_anon
            main_module.settings.rate_limit_authenticated = original_auth
            main_module.settings.rate_limit_window_seconds = original_window
            main_module.settings.rate_limit_use_forwarded_for = original_use_forwarded
            main_module._rate_limit_events.clear()

    async def test_cors_preflight_is_exempt_from_rate_limit(self, client):
        """OPTIONS preflight should not consume API request quota."""
        original_anon = main_module.settings.rate_limit_anonymous
        original_auth = main_module.settings.rate_limit_authenticated
        original_window = main_module.settings.rate_limit_window_seconds
        original_use_forwarded = main_module.settings.rate_limit_use_forwarded_for
        main_module._rate_limit_events.clear()
        try:
            main_module.settings.rate_limit_anonymous = 1
            main_module.settings.rate_limit_authenticated = 100
            main_module.settings.rate_limit_window_seconds = 60
            main_module.settings.rate_limit_use_forwarded_for = False

            preflight_headers = {
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            }

            preflight_1 = await client.options("/api/v1/connectors", headers=preflight_headers)
            preflight_2 = await client.options("/api/v1/connectors", headers=preflight_headers)
            first_get = await client.get(
                "/api/v1/connectors",
                headers={"Origin": "http://localhost:8000"},
            )
            second_get = await client.get(
                "/api/v1/connectors",
                headers={"Origin": "http://localhost:8000"},
            )

            assert preflight_1.status_code == 200
            assert preflight_2.status_code == 200
            assert first_get.status_code == 200
            assert second_get.status_code == 429
        finally:
            main_module.settings.rate_limit_anonymous = original_anon
            main_module.settings.rate_limit_authenticated = original_auth
            main_module.settings.rate_limit_window_seconds = original_window
            main_module.settings.rate_limit_use_forwarded_for = original_use_forwarded
            main_module._rate_limit_events.clear()
