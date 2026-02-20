"""Main FastAPI application."""

import uvicorn
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

from registry.config import get_settings
from registry.database import close_db, init_db
from registry.routers import connectors_router, publishers_router, tags_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Serve the registry UI."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"message": "UI not found"}


# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
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
