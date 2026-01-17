"""SQLAlchemy ORM models for the registry."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from registry.database import Base


class ConnectorCategory(str, Enum):
    """Connector category types."""

    SOURCE = "source"
    SINK = "sink"
    BIDIRECTIONAL = "bidirectional"


class ConnectorMode(str, Enum):
    """Connector execution modes."""

    STREAMING = "streaming"
    BATCH = "batch"
    BOTH = "both"


class Publisher(Base):
    """Publisher/organization that owns connectors."""

    __tablename__ = "publishers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    namespace: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    connectors: Mapped[list["Connector"]] = relationship(
        "Connector", back_populates="publisher", cascade="all, delete-orphan"
    )


class Connector(Base):
    """A connector package (one row per connector, not per version)."""

    __tablename__ = "connectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publisher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    license: Mapped[Optional[str]] = mapped_column(String(64))
    homepage: Mapped[Optional[str]] = mapped_column(String(512))
    repository: Mapped[Optional[str]] = mapped_column(String(512))
    documentation: Mapped[Optional[str]] = mapped_column(String(512))

    # Capabilities
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)

    # Status
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    deprecation_message: Mapped[Optional[str]] = mapped_column(Text)

    # Stats
    downloads_total: Mapped[int] = mapped_column(BigInteger, default=0)
    stars_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    publisher: Mapped["Publisher"] = relationship("Publisher", back_populates="connectors")
    versions: Mapped[list["ConnectorVersion"]] = relationship(
        "ConnectorVersion", back_populates="connector", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary="connector_tags", back_populates="connectors"
    )
    stars: Mapped[list["ConnectorStar"]] = relationship(
        "ConnectorStar", back_populates="connector", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("publisher_id", "name", name="uq_connector_publisher_name"),
        Index("idx_connectors_category", "category"),
        Index("idx_connectors_downloads", "downloads_total"),
        Index("idx_connectors_stars", "stars_count"),
    )


class ConnectorVersion(Base):
    """A specific version of a connector."""

    __tablename__ = "connector_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    version_major: Mapped[int] = mapped_column(Integer, nullable=False)
    version_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    version_patch: Mapped[int] = mapped_column(Integer, nullable=False)
    prerelease: Mapped[Optional[str]] = mapped_column(String(64))

    # Compatibility
    proton_version_min: Mapped[Optional[str]] = mapped_column(String(32))
    python_version_min: Mapped[Optional[str]] = mapped_column(String(32))

    # Content
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    python_code: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # Metadata
    changelog: Mapped[Optional[str]] = mapped_column(Text)
    downloads: Mapped[int] = mapped_column(BigInteger, default=0)
    yanked: Mapped[bool] = mapped_column(Boolean, default=False)
    yank_reason: Mapped[Optional[str]] = mapped_column(Text)

    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    connector: Mapped["Connector"] = relationship("Connector", back_populates="versions")
    dependencies: Mapped[list["ConnectorDependency"]] = relationship(
        "ConnectorDependency", back_populates="version", cascade="all, delete-orphan"
    )
    schema_columns: Mapped[list["ConnectorSchemaColumn"]] = relationship(
        "ConnectorSchemaColumn", back_populates="version", cascade="all, delete-orphan"
    )
    functions: Mapped[list["ConnectorFunction"]] = relationship(
        "ConnectorFunction", back_populates="version", cascade="all, delete-orphan"
    )
    config_template: Mapped[list["ConnectorConfigTemplate"]] = relationship(
        "ConnectorConfigTemplate", back_populates="version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("connector_id", "version", name="uq_version_connector_version"),
        Index("idx_versions_connector", "connector_id"),
        Index("idx_versions_published", "published_at"),
    )


class Tag(Base):
    """Tag for categorizing connectors."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    color: Mapped[Optional[str]] = mapped_column(String(7))  # Hex color

    # Relationships
    connectors: Mapped[list["Connector"]] = relationship(
        "Connector", secondary="connector_tags", back_populates="tags"
    )


class ConnectorTag(Base):
    """Many-to-many relationship between connectors and tags."""

    __tablename__ = "connector_tags"

    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class ConnectorDependency(Base):
    """Python package dependencies for a connector version."""

    __tablename__ = "connector_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connector_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    package_name: Mapped[str] = mapped_column(String(128), nullable=False)
    version_spec: Mapped[Optional[str]] = mapped_column(String(64))

    # Relationships
    version: Mapped["ConnectorVersion"] = relationship(
        "ConnectorVersion", back_populates="dependencies"
    )

    __table_args__ = (
        UniqueConstraint("version_id", "package_name", name="uq_dep_version_package"),
    )


class ConnectorSchemaColumn(Base):
    """Schema column definition for a connector version."""

    __tablename__ = "connector_schema_columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connector_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    column_name: Mapped[str] = mapped_column(String(128), nullable=False)
    column_type: Mapped[str] = mapped_column(String(64), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    version: Mapped["ConnectorVersion"] = relationship(
        "ConnectorVersion", back_populates="schema_columns"
    )

    __table_args__ = (
        UniqueConstraint("version_id", "column_name", name="uq_schema_version_column"),
    )


class ConnectorFunction(Base):
    """Function definitions (read/write) for a connector version."""

    __tablename__ = "connector_functions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connector_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    function_type: Mapped[str] = mapped_column(String(16), nullable=False)  # read or write
    function_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    version: Mapped["ConnectorVersion"] = relationship(
        "ConnectorVersion", back_populates="functions"
    )

    __table_args__ = (
        UniqueConstraint("version_id", "function_type", name="uq_func_version_type"),
    )


class ConnectorConfigTemplate(Base):
    """Configuration template items for a connector version."""

    __tablename__ = "connector_config_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connector_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    example: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    version: Mapped["ConnectorVersion"] = relationship(
        "ConnectorVersion", back_populates="config_template"
    )

    __table_args__ = (
        UniqueConstraint("version_id", "name", name="uq_config_version_name"),
    )


class ConnectorStar(Base):
    """User stars on connectors."""

    __tablename__ = "connector_stars"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    connector: Mapped["Connector"] = relationship("Connector", back_populates="stars")


class DownloadEvent(Base):
    """Download analytics events."""

    __tablename__ = "download_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connectors.id"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connector_versions.id"), nullable=False
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    proton_version: Mapped[Optional[str]] = mapped_column(String(32))
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_downloads_time", "downloaded_at"),)
