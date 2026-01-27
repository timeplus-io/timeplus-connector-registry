"""Connector service - business logic for connector operations."""

import math
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from registry.models import (
    Connector,
    ConnectorConfigTemplate,
    ConnectorDependency,
    ConnectorFunction,
    ConnectorSchemaColumn,
    ConnectorStar,
    ConnectorTag,
    ConnectorVersion,
    DownloadEvent,
    Publisher,
    Tag,
)
from registry.schemas import (
    ConnectorCategory,
    ConnectorDetail,
    ConnectorListResponse,
    ConnectorManifest,
    ConnectorSortField,
    ConnectorSummary,
    Pagination,
    SortOrder,
    VersionDetail,
    VersionListResponse,
    VersionSummary,
)
from registry.utils import compute_checksum, manifest_to_dict, parse_version


class ConnectorService:
    """Service class for connector operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_connectors(
        self,
        query: Optional[str] = None,
        category: Optional[ConnectorCategory] = None,
        tags: Optional[list[str]] = None,
        namespace: Optional[str] = None,
        verified: Optional[bool] = None,
        sort: ConnectorSortField = ConnectorSortField.DOWNLOADS,
        order: SortOrder = SortOrder.DESC,
        page: int = 1,
        per_page: int = 20,
    ) -> ConnectorListResponse:
        """List connectors with filtering and pagination."""
        # Base query
        stmt = (
            select(Connector)
            .options(
                joinedload(Connector.publisher),
                selectinload(Connector.tags),
                selectinload(Connector.versions),
            )
            .where(Connector.deprecated == False)  # noqa: E712
        )

        # Apply filters
        if query:
            search_term = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Connector.name.ilike(search_term),
                    Connector.display_name.ilike(search_term),
                    Connector.description.ilike(search_term),
                )
            )

        if category:
            stmt = stmt.where(Connector.category == category.value)

        if tags:
            # Filter by tags - connector must have all specified tags
            for tag_name in tags:
                tag_subq = (
                    select(ConnectorTag.connector_id)
                    .join(Tag)
                    .where(Tag.name == tag_name)
                )
                stmt = stmt.where(Connector.id.in_(tag_subq))

        if namespace:
            stmt = stmt.join(Publisher).where(Publisher.namespace == namespace)

        if verified is not None:
            stmt = stmt.where(Connector.verified == verified)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = {
            ConnectorSortField.DOWNLOADS: Connector.downloads_total,
            ConnectorSortField.STARS: Connector.stars_count,
            ConnectorSortField.UPDATED: Connector.updated_at,
            ConnectorSortField.CREATED: Connector.created_at,
            ConnectorSortField.NAME: Connector.name,
        }[sort]

        if order == SortOrder.DESC:
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())

        # Apply pagination
        offset = (page - 1) * per_page
        stmt = stmt.offset(offset).limit(per_page)

        # Execute
        result = await self.db.execute(stmt)
        connectors = result.unique().scalars().all()

        # Build response
        data = []
        for connector in connectors:
            latest_version = self._get_latest_version(connector.versions)
            data.append(
                ConnectorSummary(
                    namespace=connector.publisher.namespace,
                    name=connector.name,
                    displayName=connector.display_name,
                    description=connector.description,
                    category=ConnectorCategory(connector.category),
                    mode=connector.mode,
                    latestVersion=latest_version.version if latest_version else "0.0.0",
                    tags=[tag.name for tag in connector.tags],
                    downloads=connector.downloads_total,
                    stars=connector.stars_count,
                    verified=connector.verified,
                    updatedAt=connector.updated_at,
                )
            )

        return ConnectorListResponse(
            data=data,
            pagination=Pagination(
                page=page,
                perPage=per_page,
                total=total,
                totalPages=math.ceil(total / per_page) if per_page > 0 else 0,
            ),
        )

    async def get_connector(
        self, namespace: str, name: str
    ) -> Optional[ConnectorDetail]:
        """Get detailed connector information."""
        stmt = (
            select(Connector)
            .options(
                joinedload(Connector.publisher),
                selectinload(Connector.tags),
                selectinload(Connector.versions).selectinload(ConnectorVersion.dependencies),
                selectinload(Connector.versions).selectinload(ConnectorVersion.schema_columns),
                selectinload(Connector.versions).selectinload(ConnectorVersion.functions),
                selectinload(Connector.versions).selectinload(ConnectorVersion.config_template),
            )
            .join(Publisher)
            .where(Publisher.namespace == namespace)
            .where(Connector.name == name)
        )

        result = await self.db.execute(stmt)
        connector = result.unique().scalar_one_or_none()

        if connector is None:
            return None

        latest_version = self._get_latest_version(connector.versions)
        versions_list = sorted(
            [v.version for v in connector.versions if not v.yanked],
            key=lambda v: (
                *[int(x) for x in v.split("-")[0].split(".")],
                v.split("-")[1] if "-" in v else "",
            ),
            reverse=True,
        )

        # Get authors from latest manifest
        authors = None
        if latest_version and latest_version.manifest.get("metadata", {}).get("authors"):
            authors = latest_version.manifest["metadata"]["authors"]

        return ConnectorDetail(
            namespace=connector.publisher.namespace,
            name=connector.name,
            displayName=connector.display_name,
            description=connector.description,
            category=ConnectorCategory(connector.category),
            mode=connector.mode,
            latestVersion=latest_version.version if latest_version else "0.0.0",
            tags=[tag.name for tag in connector.tags],
            downloads=connector.downloads_total,
            stars=connector.stars_count,
            verified=connector.verified,
            updatedAt=connector.updated_at,
            license=connector.license,
            homepage=connector.homepage,
            repository=connector.repository,
            documentation=connector.documentation,
            authors=authors,
            versions=versions_list,
            deprecated=connector.deprecated,
            deprecationMessage=connector.deprecation_message,
            createdAt=connector.created_at,
            latestVersionDetail=self._version_to_detail(latest_version) if latest_version else None,
        )

    async def get_version(
        self, namespace: str, name: str, version: str
    ) -> Optional[VersionDetail]:
        """Get specific version details."""
        stmt = (
            select(ConnectorVersion)
            .options(
                selectinload(ConnectorVersion.dependencies),
                selectinload(ConnectorVersion.schema_columns),
                selectinload(ConnectorVersion.functions),
                selectinload(ConnectorVersion.config_template),
            )
            .join(Connector)
            .join(Publisher)
            .where(Publisher.namespace == namespace)
            .where(Connector.name == name)
            .where(ConnectorVersion.version == version)
        )

        result = await self.db.execute(stmt)
        version_obj = result.unique().scalar_one_or_none()

        if version_obj is None:
            return None

        return self._version_to_detail(version_obj)

    async def get_latest_version(
        self, namespace: str, name: str, include_prerelease: bool = False
    ) -> Optional[VersionDetail]:
        """Get latest version of a connector."""
        stmt = (
            select(ConnectorVersion)
            .options(
                selectinload(ConnectorVersion.dependencies),
                selectinload(ConnectorVersion.schema_columns),
                selectinload(ConnectorVersion.functions),
                selectinload(ConnectorVersion.config_template),
            )
            .join(Connector)
            .join(Publisher)
            .where(Publisher.namespace == namespace)
            .where(Connector.name == name)
            .where(ConnectorVersion.yanked == False)  # noqa: E712
        )

        if not include_prerelease:
            stmt = stmt.where(ConnectorVersion.prerelease.is_(None))

        stmt = stmt.order_by(
            ConnectorVersion.version_major.desc(),
            ConnectorVersion.version_minor.desc(),
            ConnectorVersion.version_patch.desc(),
        ).limit(1)

        result = await self.db.execute(stmt)
        version_obj = result.unique().scalar_one_or_none()

        if version_obj is None:
            return None

        return self._version_to_detail(version_obj)

    async def list_versions(
        self, namespace: str, name: str
    ) -> Optional[VersionListResponse]:
        """List all versions of a connector."""
        # First check if connector exists
        connector_stmt = (
            select(Connector)
            .join(Publisher)
            .where(Publisher.namespace == namespace)
            .where(Connector.name == name)
        )
        connector_result = await self.db.execute(connector_stmt)
        if connector_result.scalar_one_or_none() is None:
            return None

        stmt = (
            select(ConnectorVersion)
            .join(Connector)
            .join(Publisher)
            .where(Publisher.namespace == namespace)
            .where(Connector.name == name)
            .order_by(
                ConnectorVersion.version_major.desc(),
                ConnectorVersion.version_minor.desc(),
                ConnectorVersion.version_patch.desc(),
            )
        )

        result = await self.db.execute(stmt)
        versions = result.scalars().all()

        return VersionListResponse(
            data=[
                VersionSummary(
                    version=v.version,
                    publishedAt=v.published_at,
                    downloads=v.downloads,
                    yanked=v.yanked,
                )
                for v in versions
            ]
        )

    async def publish_connector(
        self, manifest: ConnectorManifest, publisher: Publisher
    ) -> tuple[Connector, ConnectorVersion]:
        """Publish a new connector or version."""
        metadata = manifest.metadata
        spec = manifest.spec

        # Verify namespace matches publisher
        if metadata.namespace != publisher.namespace:
            raise ValueError(
                f"Namespace '{metadata.namespace}' does not match authenticated publisher '{publisher.namespace}'"
            )

        # Parse version
        major, minor, patch, prerelease = parse_version(metadata.version)

        # Check if connector exists
        stmt = (
            select(Connector)
            .where(Connector.publisher_id == publisher.id)
            .where(Connector.name == metadata.name)
        )
        result = await self.db.execute(stmt)
        connector = result.scalar_one_or_none()

        if connector is None:
            # Create new connector
            connector = Connector(
                publisher_id=publisher.id,
                name=metadata.name,
                display_name=metadata.displayName,
                description=metadata.description,
                license=metadata.license,
                homepage=metadata.homepage,
                repository=metadata.repository,
                documentation=metadata.documentation,
                category=spec.category.value,
                mode=spec.mode.value,
            )
            self.db.add(connector)
            await self.db.flush()

            # Add tags
            await self._sync_tags(connector, spec.tags or [])
        else:
            # Update connector metadata
            connector.display_name = metadata.displayName
            connector.description = metadata.description
            connector.license = metadata.license
            connector.homepage = metadata.homepage
            connector.repository = metadata.repository
            connector.documentation = metadata.documentation
            connector.category = spec.category.value
            connector.mode = spec.mode.value

            # Update tags
            await self._sync_tags(connector, spec.tags or [])

        # Check if version already exists
        version_stmt = (
            select(ConnectorVersion)
            .where(ConnectorVersion.connector_id == connector.id)
            .where(ConnectorVersion.version == metadata.version)
        )
        version_result = await self.db.execute(version_stmt)
        if version_result.scalar_one_or_none() is not None:
            raise ValueError(f"Version {metadata.version} already exists")

        # Compute checksum
        checksum = compute_checksum(spec.pythonCode)

        # Create version
        version = ConnectorVersion(
            connector_id=connector.id,
            version=metadata.version,
            version_major=major,
            version_minor=minor,
            version_patch=patch,
            prerelease=prerelease,
            proton_version_min=spec.compatibility.protonVersion if spec.compatibility else None,
            python_version_min=spec.compatibility.pythonVersion if spec.compatibility else None,
            manifest=manifest_to_dict(manifest),
            python_code=spec.pythonCode,
            checksum_sha256=checksum,
        )
        self.db.add(version)
        await self.db.flush()

        # Add dependencies
        for dep_str in spec.dependencies or []:
            # Parse dependency string (e.g., "kafka-python>=2.0.2")
            dep_name, dep_version = self._parse_dependency(dep_str)
            dep = ConnectorDependency(
                version_id=version.id,
                package_name=dep_name,
                version_spec=dep_version,
            )
            self.db.add(dep)

        # Add schema columns
        for i, col in enumerate(spec.schema_.columns):
            schema_col = ConnectorSchemaColumn(
                version_id=version.id,
                column_name=col.name,
                column_type=col.type,
                nullable=col.nullable,
                description=col.description,
                position=i,
            )
            self.db.add(schema_col)

        # Add functions
        if spec.functions.read:
            read_func = ConnectorFunction(
                version_id=version.id,
                function_type="read",
                function_name=spec.functions.read.name,
                description=spec.functions.read.description,
            )
            self.db.add(read_func)

        if spec.functions.write:
            write_func = ConnectorFunction(
                version_id=version.id,
                function_type="write",
                function_name=spec.functions.write.name,
                description=spec.functions.write.description,
            )
            self.db.add(write_func)

        # Add config template
        for i, item in enumerate(spec.configTemplate or []):
            config = ConnectorConfigTemplate(
                version_id=version.id,
                name=item.name,
                description=item.description,
                example=item.example,
                position=i,
            )
            self.db.add(config)

        await self.db.flush()
        return connector, version

    async def yank_version(
        self, namespace: str, name: str, version: str, reason: Optional[str], publisher: Publisher
    ) -> bool:
        """Yank a version (soft delete)."""
        stmt = (
            select(ConnectorVersion)
            .join(Connector)
            .join(Publisher)
            .where(Publisher.namespace == namespace)
            .where(Publisher.id == publisher.id)
            .where(Connector.name == name)
            .where(ConnectorVersion.version == version)
        )

        result = await self.db.execute(stmt)
        version_obj = result.scalar_one_or_none()

        if version_obj is None:
            return False

        version_obj.yanked = True
        version_obj.yank_reason = reason
        return True

    async def record_download(
        self, namespace: str, name: str, version: str, proton_version: Optional[str] = None
    ) -> bool:
        """Record a download event and increment counters."""
        # Get connector and version
        stmt = (
            select(ConnectorVersion, Connector)
            .join(Connector)
            .join(Publisher)
            .where(Publisher.namespace == namespace)
            .where(Connector.name == name)
            .where(ConnectorVersion.version == version)
        )

        result = await self.db.execute(stmt)
        row = result.one_or_none()

        if row is None:
            return False

        version_obj, connector = row

        # Increment counters
        version_obj.downloads += 1
        connector.downloads_total += 1

        # Record event
        event = DownloadEvent(
            connector_id=connector.id,
            version_id=version_obj.id,
            proton_version=proton_version,
        )
        self.db.add(event)

        return True

    async def star_connector(self, namespace: str, name: str, user_id: UUID) -> bool:
        """Star a connector."""
        stmt = (
            select(Connector)
            .join(Publisher)
            .where(Publisher.namespace == namespace)
            .where(Connector.name == name)
        )

        result = await self.db.execute(stmt)
        connector = result.scalar_one_or_none()

        if connector is None:
            return False

        # Check if already starred
        star_stmt = select(ConnectorStar).where(
            ConnectorStar.connector_id == connector.id,
            ConnectorStar.user_id == user_id,
        )
        star_result = await self.db.execute(star_stmt)
        if star_result.scalar_one_or_none() is not None:
            return True  # Already starred

        # Add star
        star = ConnectorStar(connector_id=connector.id, user_id=user_id)
        self.db.add(star)
        connector.stars_count += 1

        return True

    async def unstar_connector(self, namespace: str, name: str, user_id: UUID) -> bool:
        """Remove star from a connector."""
        stmt = (
            select(Connector)
            .join(Publisher)
            .where(Publisher.namespace == namespace)
            .where(Connector.name == name)
        )

        result = await self.db.execute(stmt)
        connector = result.scalar_one_or_none()

        if connector is None:
            return False

        # Find and remove star
        star_stmt = select(ConnectorStar).where(
            ConnectorStar.connector_id == connector.id,
            ConnectorStar.user_id == user_id,
        )
        star_result = await self.db.execute(star_stmt)
        star = star_result.scalar_one_or_none()

        if star is None:
            return True  # Not starred

        await self.db.delete(star)
        connector.stars_count = max(0, connector.stars_count - 1)

        return True

    def _get_latest_version(
        self, versions: list[ConnectorVersion]
    ) -> Optional[ConnectorVersion]:
        """Get the latest non-yanked version."""
        stable_versions = [v for v in versions if not v.yanked and v.prerelease is None]
        if stable_versions:
            return max(
                stable_versions,
                key=lambda v: (v.version_major, v.version_minor, v.version_patch),
            )

        # Fall back to prerelease if no stable
        non_yanked = [v for v in versions if not v.yanked]
        if non_yanked:
            return max(
                non_yanked,
                key=lambda v: (v.version_major, v.version_minor, v.version_patch),
            )

        return None

    def _version_to_detail(self, version: ConnectorVersion) -> VersionDetail:
        """Convert version model to detail schema."""
        manifest = version.manifest
        spec = manifest.get("spec", {})

        # Build functions response
        functions_data = {}
        for func in version.functions:
            functions_data[func.function_type] = {
                "name": func.function_name,
                "description": func.description,
            }

        return VersionDetail(
            version=version.version,
            publishedAt=version.published_at,
            downloads=version.downloads,
            checksum=version.checksum_sha256,
            changelog=version.changelog,
            yanked=version.yanked,
            yankReason=version.yank_reason,
            compatibility={
                "protonVersion": version.proton_version_min,
                "pythonVersion": version.python_version_min,
            },
            dependencies=[
                {"name": d.package_name, "version": d.version_spec}
                for d in version.dependencies
            ],
            schema={
                "columns": [
                    {
                        "name": c.column_name,
                        "type": c.column_type,
                        "nullable": c.nullable,
                        "description": c.description,
                    }
                    for c in sorted(version.schema_columns, key=lambda x: x.position)
                ]
            },
            functions=functions_data,
            configTemplate=[
                {
                    "name": c.name,
                    "description": c.description,
                    "example": c.example,
                }
                for c in sorted(version.config_template, key=lambda x: x.position)
            ],
            examples=spec.get("examples", []),
            pythonCode=version.python_code,
        )

    async def _sync_tags(self, connector: Connector, tag_names: list[str]) -> None:
        """Sync connector tags."""
        # Remove existing tags
        await self.db.execute(
            ConnectorTag.__table__.delete().where(
                ConnectorTag.connector_id == connector.id
            )
        )

        # Add new tags
        for tag_name in tag_names:
            # Get or create tag
            tag_stmt = select(Tag).where(Tag.name == tag_name)
            tag_result = await self.db.execute(tag_stmt)
            tag = tag_result.scalar_one_or_none()

            if tag is None:
                tag = Tag(name=tag_name)
                self.db.add(tag)
                await self.db.flush()

            # Create association
            connector_tag = ConnectorTag(connector_id=connector.id, tag_id=tag.id)
            self.db.add(connector_tag)

    def _parse_dependency(self, dep_str: str) -> tuple[str, Optional[str]]:
        """Parse a dependency string like 'package>=1.0.0'."""
        import re

        match = re.match(r"^([a-zA-Z0-9_-]+)(.*)$", dep_str)
        if match:
            name = match.group(1)
            version = match.group(2) if match.group(2) else None
            return name, version
        return dep_str, None
