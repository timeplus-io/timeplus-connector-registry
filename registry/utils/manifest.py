"""Manifest parsing and validation utilities."""

import hashlib
import re
from typing import Any, Optional

import semver
import yaml
from pydantic import ValidationError

from registry.schemas import ConnectorManifest


class ManifestError(Exception):
    """Error in manifest parsing or validation."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


def parse_manifest(content: str) -> ConnectorManifest:
    """
    Parse and validate a connector manifest from YAML string.

    Args:
        content: YAML content string

    Returns:
        Validated ConnectorManifest object

    Raises:
        ManifestError: If parsing or validation fails
    """
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ManifestError(f"Invalid YAML: {e}")

    if not isinstance(data, dict):
        raise ManifestError("Manifest must be a YAML object")

    try:
        manifest = ConnectorManifest.model_validate(data)
    except ValidationError as e:
        errors = []
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            errors.append(f"{loc}: {error['msg']}")
        raise ManifestError("Manifest validation failed", {"errors": errors})

    # Additional validation
    _validate_manifest(manifest)

    return manifest


def _validate_manifest(manifest: ConnectorManifest) -> None:
    """Perform additional validation on the manifest."""
    spec = manifest.spec
    functions = spec.functions

    # Validate category matches functions
    if spec.category == "source":
        if functions.read is None:
            raise ManifestError("Source connectors must have a read function")
        if functions.write is not None:
            raise ManifestError("Source connectors should not have a write function")

    elif spec.category == "sink":
        if functions.write is None:
            raise ManifestError("Sink connectors must have a write function")
        if functions.read is not None:
            raise ManifestError("Sink connectors should not have a read function")

    elif spec.category == "bidirectional":
        if functions.read is None or functions.write is None:
            raise ManifestError(
                "Bidirectional connectors must have both read and write functions"
            )

    # Validate function names exist in Python code
    python_code = spec.pythonCode
    if functions.read and not _function_exists(python_code, functions.read.name):
        raise ManifestError(
            f"Read function '{functions.read.name}' not found in Python code"
        )

    if functions.write and not _function_exists(python_code, functions.write.name):
        raise ManifestError(
            f"Write function '{functions.write.name}' not found in Python code"
        )

    # Validate schema has at least one column
    if not spec.schema_.columns:
        raise ManifestError("Schema must have at least one column")


def _function_exists(code: str, function_name: str) -> bool:
    """Check if a function definition exists in Python code."""
    pattern = rf"def\s+{re.escape(function_name)}\s*\("
    return bool(re.search(pattern, code))


def parse_version(version_str: str) -> tuple[int, int, int, Optional[str]]:
    """
    Parse a semver version string.

    Args:
        version_str: Version string (e.g., "1.2.3", "1.0.0-beta.1")

    Returns:
        Tuple of (major, minor, patch, prerelease)

    Raises:
        ManifestError: If version is invalid
    """
    try:
        v = semver.Version.parse(version_str)
        return v.major, v.minor, v.patch, v.prerelease
    except ValueError as e:
        raise ManifestError(f"Invalid version '{version_str}': {e}")


def compute_checksum(content: str) -> str:
    """Compute SHA-256 checksum of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def manifest_to_dict(manifest: ConnectorManifest) -> dict[str, Any]:
    """Convert manifest to dictionary for storage."""
    return manifest.model_dump(mode="json", by_alias=True)
