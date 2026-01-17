"""Publisher service - business logic for publisher operations."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from registry.models import Connector, Publisher
from registry.schemas import PublisherDetailResponse, PublisherResponse
from registry.utils import get_password_hash


class PublisherService:
    """Service class for publisher operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_publisher(
        self,
        namespace: str,
        display_name: str,
        email: str,
        password: str,
    ) -> Publisher:
        """Create a new publisher."""
        # Check if namespace exists
        stmt = select(Publisher).where(Publisher.namespace == namespace)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ValueError(f"Namespace '{namespace}' already exists")

        # Check if email exists
        stmt = select(Publisher).where(Publisher.email == email)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ValueError(f"Email '{email}' already registered")

        publisher = Publisher(
            namespace=namespace,
            display_name=display_name,
            email=email,
            api_key_hash=get_password_hash(password),
        )
        self.db.add(publisher)
        await self.db.flush()

        return publisher

    async def get_publisher(self, namespace: str) -> Optional[PublisherResponse]:
        """Get publisher information."""
        stmt = (
            select(Publisher)
            .options(selectinload(Publisher.connectors))
            .where(Publisher.namespace == namespace)
        )
        result = await self.db.execute(stmt)
        publisher = result.unique().scalar_one_or_none()

        if publisher is None:
            return None

        # Calculate total downloads
        total_downloads = sum(c.downloads_total for c in publisher.connectors)

        return PublisherResponse(
            namespace=publisher.namespace,
            displayName=publisher.display_name,
            verified=publisher.verified,
            connectorCount=len(publisher.connectors),
            totalDownloads=total_downloads,
        )

    async def get_publisher_detail(
        self, namespace: str
    ) -> Optional[PublisherDetailResponse]:
        """Get detailed publisher information."""
        stmt = (
            select(Publisher)
            .options(selectinload(Publisher.connectors))
            .where(Publisher.namespace == namespace)
        )
        result = await self.db.execute(stmt)
        publisher = result.unique().scalar_one_or_none()

        if publisher is None:
            return None

        total_downloads = sum(c.downloads_total for c in publisher.connectors)

        return PublisherDetailResponse(
            namespace=publisher.namespace,
            displayName=publisher.display_name,
            email=publisher.email,
            verified=publisher.verified,
            connectorCount=len(publisher.connectors),
            totalDownloads=total_downloads,
            createdAt=publisher.created_at,
        )
