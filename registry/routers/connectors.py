"""Connector API routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from registry.config import get_settings
from registry.database import get_db
from registry.models import Publisher
from registry.schemas import (
    ConnectorCategory,
    ConnectorDetail,
    ConnectorListResponse,
    ConnectorManifest,
    ConnectorSortField,
    ErrorResponse,
    PublishResponse,
    SortOrder,
    VersionDetail,
    VersionListResponse,
    YankRequest,
)
from registry.services import ConnectorService
from registry.utils import (
    ManifestError,
    generate_install_sql,
    get_current_publisher,
    get_required_publisher,
    parse_manifest,
)

router = APIRouter(prefix="/connectors", tags=["Connectors"])
settings = get_settings()


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[ConnectorCategory] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    namespace: Optional[str] = Query(None, description="Filter by publisher namespace"),
    verified: Optional[bool] = Query(None, description="Filter by verified status"),
    sort: ConnectorSortField = Query(
        ConnectorSortField.DOWNLOADS, description="Sort field"
    ),
    order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description="Items per page",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    List and search connectors.

    Filter by category, tags, namespace, or search by keyword.
    """
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    service = ConnectorService(db)
    return await service.list_connectors(
        query=q,
        category=category,
        tags=tag_list,
        namespace=namespace,
        verified=verified,
        sort=sort,
        order=order,
        page=page,
        per_page=per_page,
    )


@router.get("/{namespace}/{name}", response_model=ConnectorDetail)
async def get_connector(
    namespace: str,
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a connector."""
    service = ConnectorService(db)
    connector = await service.get_connector(namespace, name)

    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{namespace}/{name}' not found",
        )

    return connector


@router.get("/{namespace}/{name}/versions", response_model=VersionListResponse)
async def list_versions(
    namespace: str,
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """List all versions of a connector."""
    service = ConnectorService(db)
    versions = await service.list_versions(namespace, name)

    if versions is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{namespace}/{name}' not found",
        )

    return versions


@router.get("/{namespace}/{name}/versions/latest", response_model=VersionDetail)
async def get_latest_version(
    namespace: str,
    name: str,
    include_prerelease: bool = Query(False, description="Include prerelease versions"),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest version of a connector."""
    service = ConnectorService(db)
    version = await service.get_latest_version(namespace, name, include_prerelease)

    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No versions found for connector '{namespace}/{name}'",
        )

    return version


@router.get("/{namespace}/{name}/versions/{version}", response_model=VersionDetail)
async def get_version(
    namespace: str,
    name: str,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """Get specific version details."""
    service = ConnectorService(db)
    version_detail = await service.get_version(namespace, name, version)

    if version_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version}' not found for connector '{namespace}/{name}'",
        )

    return version_detail


@router.get(
    "/{namespace}/{name}/sql",
    response_class=PlainTextResponse,
    responses={
        200: {
            "content": {"text/plain": {}},
            "description": "Installation SQL script",
        }
    },
)
async def get_install_sql(
    namespace: str,
    name: str,
    version: Optional[str] = Query(None, description="Specific version (defaults to latest)"),
    stream_name: Optional[str] = Query(None, alias="name", description="Custom stream name"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get installation SQL for a connector.

    Returns ready-to-execute SQL that installs dependencies and creates the external stream.
    """
    service = ConnectorService(db)

    if version:
        version_detail = await service.get_version(namespace, name, version)
    else:
        version_detail = await service.get_latest_version(namespace, name)

    if version_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{namespace}/{name}' not found",
        )

    # Get the full manifest from version
    stmt_version = await service.get_version(namespace, name, version_detail.version)
    
    # Reconstruct manifest for SQL generation
    manifest = {
        "metadata": {
            "namespace": namespace,
            "name": name,
            "version": version_detail.version,
        },
        "spec": {
            "category": version_detail.functions.get("read") and version_detail.functions.get("write") 
                and "bidirectional" 
                or (version_detail.functions.get("write") and "sink" or "source"),
            "mode": "streaming",  # Default
            "dependencies": [
                f"{d.name}{d.version or ''}" for d in version_detail.dependencies
            ] if hasattr(version_detail, 'dependencies') else [
                f"{d['name']}{d.get('version', '')}" for d in version_detail.dependencies
            ],
            "schema": version_detail.schema_ if hasattr(version_detail, 'schema_') else version_detail.schema,
            "functions": version_detail.functions,
            "pythonCode": version_detail.pythonCode,
        },
    }

    # Record download
    await service.record_download(namespace, name, version_detail.version)

    sql = generate_install_sql(manifest, stream_name)
    return PlainTextResponse(content=sql, media_type="text/plain")


@router.get(
    "/{namespace}/{name}/code",
    response_class=PlainTextResponse,
    responses={
        200: {
            "content": {"text/x-python": {}},
            "description": "Python source code",
        }
    },
)
async def get_python_code(
    namespace: str,
    name: str,
    version: Optional[str] = Query(None, description="Specific version"),
    db: AsyncSession = Depends(get_db),
):
    """Get the Python code for a connector."""
    service = ConnectorService(db)

    if version:
        version_detail = await service.get_version(namespace, name, version)
    else:
        version_detail = await service.get_latest_version(namespace, name)

    if version_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{namespace}/{name}' not found",
        )

    return PlainTextResponse(content=version_detail.pythonCode, media_type="text/x-python")


@router.post(
    "",
    response_model=PublishResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def publish_connector(
    request: Request,
    publisher: Publisher = Depends(get_required_publisher),
    db: AsyncSession = Depends(get_db),
):
    """
    Publish a new connector or version.

    Accepts connector.yaml content as the request body.
    """
    # Read raw body
    body = await request.body()
    content = body.decode("utf-8")

    # Parse manifest
    try:
        manifest = parse_manifest(content)
    except ManifestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid manifest", "message": e.message, "details": e.details},
        )

    # Publish
    service = ConnectorService(db)
    try:
        connector, version = await service.publish_connector(manifest, publisher)
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return PublishResponse(
        namespace=publisher.namespace,
        name=connector.name,
        version=version.version,
        downloadUrl=f"{settings.api_v1_prefix}/connectors/{publisher.namespace}/{connector.name}/sql?version={version.version}",
        message=f"Successfully published {publisher.namespace}/{connector.name}@{version.version}",
    )


@router.post(
    "/{namespace}/{name}/versions/{version}/yank",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def yank_version(
    namespace: str,
    name: str,
    version: str,
    yank_request: Optional[YankRequest] = None,
    publisher: Publisher = Depends(get_required_publisher),
    db: AsyncSession = Depends(get_db),
):
    """
    Yank a version (soft delete).

    Yanked versions are hidden from listings but can still be downloaded directly.
    """
    if publisher.namespace != namespace:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only yank versions from your own namespace",
        )

    service = ConnectorService(db)
    reason = yank_request.reason if yank_request else None
    success = await service.yank_version(namespace, name, version, reason, publisher)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version}' not found for connector '{namespace}/{name}'",
        )

    return {"message": f"Version {version} has been yanked"}


@router.post("/{namespace}/{name}/star", status_code=status.HTTP_200_OK)
async def star_connector(
    namespace: str,
    name: str,
    publisher: Publisher = Depends(get_required_publisher),
    db: AsyncSession = Depends(get_db),
):
    """Star a connector."""
    service = ConnectorService(db)
    success = await service.star_connector(namespace, name, publisher.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{namespace}/{name}' not found",
        )

    return {"message": "Starred"}


@router.delete("/{namespace}/{name}/star", status_code=status.HTTP_200_OK)
async def unstar_connector(
    namespace: str,
    name: str,
    publisher: Publisher = Depends(get_required_publisher),
    db: AsyncSession = Depends(get_db),
):
    """Remove star from a connector."""
    service = ConnectorService(db)
    success = await service.unstar_connector(namespace, name, publisher.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{namespace}/{name}' not found",
        )

    return {"message": "Unstarred"}
