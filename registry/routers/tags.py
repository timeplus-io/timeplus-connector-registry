"""Tag and category API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from registry.database import get_db
from registry.schemas import CategoryStats, ConnectorListResponse, TagResponse
from registry.services import ConnectorService, TagService

router = APIRouter(tags=["Tags & Categories"])


@router.get("/tags", response_model=list[TagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
):
    """List all tags with connector counts."""
    service = TagService(db)
    return await service.list_tags()


@router.get("/tags/{tag}/connectors", response_model=ConnectorListResponse)
async def get_connectors_by_tag(
    tag: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all connectors with a specific tag."""
    connector_service = ConnectorService(db)
    return await connector_service.list_connectors(tags=[tag])


@router.get("/categories", response_model=CategoryStats)
async def get_category_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get connector counts by category."""
    service = TagService(db)
    return await service.get_category_stats()
