"""Tag service - business logic for tag operations."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.models import Connector, ConnectorTag, Tag
from registry.schemas import CategoryStats, TagResponse


class TagService:
    """Service class for tag operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tags(self) -> list[TagResponse]:
        """List all tags with connector counts."""
        stmt = (
            select(Tag, func.count(ConnectorTag.connector_id).label("count"))
            .outerjoin(ConnectorTag)
            .group_by(Tag.id)
            .order_by(func.count(ConnectorTag.connector_id).desc())
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            TagResponse(
                name=tag.name,
                description=tag.description,
                count=count,
                color=tag.color,
            )
            for tag, count in rows
        ]

    async def get_category_stats(self) -> CategoryStats:
        """Get connector counts by category."""
        stmt = select(
            Connector.category, func.count(Connector.id).label("count")
        ).group_by(Connector.category)

        result = await self.db.execute(stmt)
        rows = result.all()

        stats = {"source": 0, "sink": 0, "bidirectional": 0}
        for category, count in rows:
            if category in stats:
                stats[category] = count

        return CategoryStats(**stats)
