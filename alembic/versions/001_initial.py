"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2025-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Publishers table
    op.create_table(
        "publishers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("namespace", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, default=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace"),
    )
    op.create_index("idx_publishers_namespace", "publishers", ["namespace"])

    # Tags table
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Connectors table
    op.create_table(
        "connectors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("publisher_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("license", sa.String(64), nullable=True),
        sa.Column("homepage", sa.String(512), nullable=True),
        sa.Column("repository", sa.String(512), nullable=True),
        sa.Column("documentation", sa.String(512), nullable=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, default=False),
        sa.Column("deprecated", sa.Boolean(), nullable=False, default=False),
        sa.Column("deprecation_message", sa.Text(), nullable=True),
        sa.Column("downloads_total", sa.BigInteger(), nullable=False, default=0),
        sa.Column("stars_count", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["publisher_id"], ["publishers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publisher_id", "name", name="uq_connector_publisher_name"),
    )
    op.create_index("idx_connectors_category", "connectors", ["category"])
    op.create_index("idx_connectors_downloads", "connectors", ["downloads_total"])
    op.create_index("idx_connectors_stars", "connectors", ["stars_count"])

    # Connector versions table
    op.create_table(
        "connector_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("connector_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("version_major", sa.Integer(), nullable=False),
        sa.Column("version_minor", sa.Integer(), nullable=False),
        sa.Column("version_patch", sa.Integer(), nullable=False),
        sa.Column("prerelease", sa.String(64), nullable=True),
        sa.Column("proton_version_min", sa.String(32), nullable=True),
        sa.Column("python_version_min", sa.String(32), nullable=True),
        sa.Column("manifest", sa.Text(), nullable=False),
        sa.Column("python_code", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("downloads", sa.BigInteger(), nullable=False, default=0),
        sa.Column("yanked", sa.Boolean(), nullable=False, default=False),
        sa.Column("yank_reason", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connector_id", "version", name="uq_version_connector_version"),
    )
    op.create_index("idx_versions_connector", "connector_versions", ["connector_id"])
    op.create_index("idx_versions_published", "connector_versions", ["published_at"])

    # Connector tags (many-to-many)
    op.create_table(
        "connector_tags",
        sa.Column("connector_id", sa.UUID(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("connector_id", "tag_id"),
    )

    # Connector dependencies
    op.create_table(
        "connector_dependencies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("package_name", sa.String(128), nullable=False),
        sa.Column("version_spec", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["version_id"], ["connector_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "package_name", name="uq_dep_version_package"),
    )

    # Connector schema columns
    op.create_table(
        "connector_schema_columns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("column_name", sa.String(128), nullable=False),
        sa.Column("column_type", sa.String(64), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False, default=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["connector_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "column_name", name="uq_schema_version_column"),
    )

    # Connector functions
    op.create_table(
        "connector_functions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("function_type", sa.String(16), nullable=False),
        sa.Column("function_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["version_id"], ["connector_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "function_type", name="uq_func_version_type"),
    )

    # Connector config template
    op.create_table(
        "connector_config_template",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("example", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["connector_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "name", name="uq_config_version_name"),
    )

    # Connector stars
    op.create_table(
        "connector_stars",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("connector_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "connector_id"),
    )

    # Download events
    op.create_table(
        "download_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("connector_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("proton_version", sa.String(32), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["connector_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_downloads_time", "download_events", ["downloaded_at"])


def downgrade() -> None:
    op.drop_table("download_events")
    op.drop_table("connector_stars")
    op.drop_table("connector_config_template")
    op.drop_table("connector_functions")
    op.drop_table("connector_schema_columns")
    op.drop_table("connector_dependencies")
    op.drop_table("connector_tags")
    op.drop_table("connector_versions")
    op.drop_table("connectors")
    op.drop_table("tags")
    op.drop_table("publishers")
