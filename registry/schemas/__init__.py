"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ============ Enums ============


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


class SortOrder(str, Enum):
    """Sort order options."""

    ASC = "asc"
    DESC = "desc"


class ConnectorSortField(str, Enum):
    """Fields to sort connectors by."""

    DOWNLOADS = "downloads"
    STARS = "stars"
    UPDATED = "updated"
    CREATED = "created"
    NAME = "name"


# ============ Base Schemas ============


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True)


# ============ Author ============


class Author(BaseModel):
    """Connector author information."""

    name: str
    email: Optional[EmailStr] = None


# ============ Schema Column ============


class SchemaColumn(BaseModel):
    """Column definition for connector schema."""

    name: str = Field(..., min_length=1, max_length=128)
    type: str = Field(..., min_length=1, max_length=64)
    nullable: bool = True
    description: Optional[str] = None


class SchemaColumnResponse(BaseSchema):
    """Schema column response."""

    name: str
    type: str
    nullable: bool
    description: Optional[str]


# ============ Function Definition ============


class FunctionDef(BaseModel):
    """Function definition for read/write operations."""

    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None


class FunctionDefResponse(BaseSchema):
    """Function definition response."""

    name: str
    description: Optional[str]


# ============ Config Template ============


class ConfigTemplateItem(BaseModel):
    """Configuration template item."""

    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    example: Optional[str] = None


class ConfigTemplateItemResponse(BaseSchema):
    """Config template item response."""

    name: str
    description: Optional[str]
    example: Optional[str]


# ============ Dependency ============


class Dependency(BaseModel):
    """Python package dependency."""

    name: str
    version: Optional[str] = None


class DependencyResponse(BaseSchema):
    """Dependency response."""

    name: str
    version: Optional[str]


# ============ Example ============


class Example(BaseModel):
    """Usage example."""

    title: str
    description: Optional[str] = None
    code: str


class ExampleResponse(BaseSchema):
    """Example response."""

    title: str
    description: Optional[str]
    code: str


# ============ Compatibility ============


class Compatibility(BaseModel):
    """Version compatibility information."""

    protonVersion: Optional[str] = None
    pythonVersion: Optional[str] = None


class CompatibilityResponse(BaseSchema):
    """Compatibility response."""

    protonVersion: Optional[str]
    pythonVersion: Optional[str]


# ============ Functions Container ============


class Functions(BaseModel):
    """Container for read/write function definitions."""

    read: Optional[FunctionDef] = None
    write: Optional[FunctionDef] = None


class FunctionsResponse(BaseSchema):
    """Functions container response."""

    read: Optional[FunctionDefResponse] = None
    write: Optional[FunctionDefResponse] = None


# ============ Schema Container ============


class Schema(BaseModel):
    """Schema definition container."""

    columns: list[SchemaColumn]


class SchemaResponse(BaseSchema):
    """Schema response."""

    columns: list[SchemaColumnResponse]


# ============ Connector Manifest ============


class ConnectorMetadata(BaseModel):
    """Connector metadata from manifest."""

    name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    namespace: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")
    displayName: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    authors: Optional[list[Author]] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    documentation: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class ConnectorSpec(BaseModel):
    """Connector specification from manifest."""

    category: ConnectorCategory
    mode: ConnectorMode
    tags: Optional[list[str]] = None
    compatibility: Optional[Compatibility] = None
    dependencies: Optional[list[str]] = None
    schema_: Schema = Field(..., alias="schema")
    functions: Functions
    configTemplate: Optional[list[ConfigTemplateItem]] = None
    pythonCode: str = Field(..., min_length=1)
    examples: Optional[list[Example]] = None

    model_config = ConfigDict(populate_by_name=True)


class ConnectorManifest(BaseModel):
    """Complete connector manifest (connector.yaml)."""

    apiVersion: str = "v1"
    kind: str = "Connector"
    metadata: ConnectorMetadata
    spec: ConnectorSpec

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if v != "Connector":
            raise ValueError("kind must be 'Connector'")
        return v


# ============ Tag ============


class TagResponse(BaseSchema):
    """Tag response."""

    name: str
    description: Optional[str]
    count: int = 0
    color: Optional[str] = None


# ============ Publisher ============


class PublisherCreate(BaseModel):
    """Publisher registration request."""

    namespace: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    display_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class PublisherResponse(BaseSchema):
    """Publisher response."""

    namespace: str
    displayName: str
    verified: bool
    connectorCount: int = 0
    totalDownloads: int = 0


class PublisherDetailResponse(PublisherResponse):
    """Detailed publisher response."""

    email: str
    createdAt: datetime


# ============ Connector Summary (List View) ============


class ConnectorSummary(BaseSchema):
    """Connector summary for list views."""

    namespace: str
    name: str
    displayName: str
    description: Optional[str]
    category: ConnectorCategory
    mode: ConnectorMode
    latestVersion: str
    tags: list[str]
    downloads: int
    stars: int
    verified: bool
    updatedAt: datetime


# ============ Connector Detail ============


class ConnectorDetail(ConnectorSummary):
    """Detailed connector information."""

    license: Optional[str]
    homepage: Optional[str]
    repository: Optional[str]
    documentation: Optional[str]
    authors: Optional[list[Author]]
    versions: list[str]
    deprecated: bool
    deprecationMessage: Optional[str]
    createdAt: datetime
    latestVersionDetail: Optional["VersionDetail"] = None


# ============ Version ============


class VersionSummary(BaseSchema):
    """Version summary for list views."""

    version: str
    publishedAt: datetime
    downloads: int
    yanked: bool


class VersionDetail(BaseSchema):
    """Detailed version information."""

    version: str
    publishedAt: datetime
    downloads: int
    checksum: str
    changelog: Optional[str]
    yanked: bool
    yankReason: Optional[str]
    compatibility: CompatibilityResponse
    dependencies: list[DependencyResponse]
    schema_: SchemaResponse = Field(..., alias="schema")
    functions: FunctionsResponse
    configTemplate: list[ConfigTemplateItemResponse]
    examples: list[ExampleResponse]
    pythonCode: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ============ Pagination ============


class Pagination(BaseModel):
    """Pagination information."""

    page: int
    perPage: int
    total: int
    totalPages: int


# ============ List Responses ============


class ConnectorListResponse(BaseModel):
    """Paginated connector list response."""

    data: list[ConnectorSummary]
    pagination: Pagination


class VersionListResponse(BaseModel):
    """Version list response."""

    data: list[VersionSummary]


# ============ Publish Response ============


class PublishResponse(BaseModel):
    """Connector publish response."""

    namespace: str
    name: str
    version: str
    downloadUrl: str
    message: str


# ============ Category Stats ============


class CategoryStats(BaseModel):
    """Category statistics."""

    source: int
    sink: int
    bidirectional: int


# ============ Auth ============


class Token(BaseModel):
    """Authentication token response."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data."""

    namespace: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request."""

    namespace: str
    password: str


# ============ Yank Request ============


class YankRequest(BaseModel):
    """Version yank request."""

    reason: Optional[str] = None


# ============ Error Response ============


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    message: str
    details: Optional[dict[str, Any]] = None


# Forward reference resolution
ConnectorDetail.model_rebuild()
