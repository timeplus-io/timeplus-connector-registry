"""Main FastAPI application."""

import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from registry.config import get_settings
from registry.database import close_db, init_db
from registry.routers import connectors_router, publishers_router, tags_router
from registry.utils.auth import decode_token

settings = get_settings()
_rate_limit_events: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = asyncio.Lock()


def _prune_rate_limit_buckets(cutoff: float) -> None:
    """Remove expired events and drop empty buckets to bound memory usage."""
    stale_keys: list[str] = []
    for key, events in _rate_limit_events.items():
        while events and events[0] < cutoff:
            events.popleft()
        if not events:
            stale_keys.append(key)

    for key in stale_keys:
        _rate_limit_events.pop(key, None)


def _get_rate_limit_client_host(request: Request) -> str:
    """Resolve client host, optionally honoring trusted proxy headers."""
    if settings.rate_limit_use_forwarded_for:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            for item in forwarded_for.split(","):
                candidate = item.strip()
                if candidate:
                    return candidate

        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip

    return request.client.host if request.client else "unknown"


def _apply_cors_headers(request: Request, response: JSONResponse) -> JSONResponse:
    """Add minimal CORS headers for middleware-generated responses."""
    origin = request.headers.get("origin")
    if not origin:
        return response

    allow_all_origins = "*" in settings.cors_origins
    if allow_all_origins and not settings.cors_allow_credentials:
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
    elif allow_all_origins or origin in settings.cors_origins:
        response.headers.setdefault("Access-Control-Allow-Origin", origin)
        vary = response.headers.get("Vary")
        if vary:
            vary_values = [value.strip().lower() for value in vary.split(",")]
            if "origin" not in vary_values:
                response.headers["Vary"] = f"{vary}, Origin"
        else:
            response.headers["Vary"] = "Origin"
    else:
        return response

    if settings.cors_allow_credentials:
        response.headers.setdefault("Access-Control-Allow-Credentials", "true")

    return response


def _rate_limited_response(request: Request, retry_after: int) -> JSONResponse:
    """Build a consistent 429 response and apply CORS headers."""
    rate_limited = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "rate_limit_exceeded",
            "message": "Rate limit exceeded",
        },
        headers={"Retry-After": str(retry_after)},
    )
    return _apply_cors_headers(request, rate_limited)


def _is_cors_preflight(request: Request) -> bool:
    """Detect browser CORS preflight requests."""
    return (
        request.method == "OPTIONS"
        and "origin" in request.headers
        and "access-control-request-method" in request.headers
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## Timeplus Connector Registry

Central registry for Timeplus Custom Table Function (CTF) connectors.

### Features

- **Browse** - Search and discover connectors by category, tags, or keywords
- **Download** - Get installation SQL for any connector
- **Publish** - Share your connectors with the community

### Authentication

Most read operations are public. Publishing requires authentication:

1. Register at `/api/v1/register`
2. Use the returned token in the `Authorization: Bearer <token>` header

### Quick Start

```bash
# Search for connectors
curl "http://localhost:8000/api/v1/connectors?q=kafka"

# Get installation SQL
curl "http://localhost:8000/api/v1/connectors/timeplus/kafka-reader/sql"
```
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Apply a simple in-memory request limiter for API routes."""
    if not request.url.path.startswith(settings.api_v1_prefix):
        return await call_next(request)
    if _is_cors_preflight(request):
        return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
    token_data = decode_token(token) if token else None
    if token_data is not None and token_data.namespace:
        client_key = f"auth:{token_data.namespace}"
        limit = settings.rate_limit_authenticated
    else:
        client_host = _get_rate_limit_client_host(request)
        client_key = f"ip:{client_host}"
        limit = settings.rate_limit_anonymous

    now = time.monotonic()
    cutoff = now - settings.rate_limit_window_seconds
    reset_after = settings.rate_limit_window_seconds

    async with _rate_limit_lock:
        _prune_rate_limit_buckets(cutoff)
        events = _rate_limit_events[client_key]

        if limit <= 0:
            return _rate_limited_response(request, settings.rate_limit_window_seconds)

        if len(events) >= limit:
            oldest_event = events[0] if events else now
            retry_after = int(max(1, settings.rate_limit_window_seconds - (now - oldest_event)))
            return _rate_limited_response(request, retry_after)

        events.append(now)
        remaining = max(0, limit - len(events))
        if events:
            reset_after = int(max(1, settings.rate_limit_window_seconds - (now - events[0])))

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_after)
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "details": {"type": type(exc).__name__} if settings.debug else None,
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


# Root endpoint
@app.get("/", tags=["Root"], response_model=None)
async def root() -> Response:
    """Serve the registry UI."""
    html_path = Path(__file__).with_name("static") / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    return JSONResponse(content={"message": "UI not found"})


# Mount static files directory
static_dir = Path(__file__).with_name("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routers
app.include_router(connectors_router, prefix=settings.api_v1_prefix)
app.include_router(publishers_router, prefix=settings.api_v1_prefix)
app.include_router(tags_router, prefix=settings.api_v1_prefix)


def run() -> None:
    """Run the application with uvicorn."""
    uvicorn.run(
        "registry.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
