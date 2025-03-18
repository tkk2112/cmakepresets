import json
from pathlib import Path
from typing import Any, Final, cast

import jsonschema
import requests

from . import logger as mainLogger
from .exceptions import SchemaDownloadError, VersionError

logger: Final = mainLogger.getChild(__name__)

# Schema version to CMake version mapping
_schema_version_cmake_version: Final = {
    1: (3, 19, 0),
    2: (3, 20, 0),
    3: (3, 21, 0),
    4: (3, 23, 0),
    5: (3, 24, 0),
    6: (3, 25, 0),
    7: (3, 27, 0),
    8: (3, 28, 0),
    9: (3, 30, 0),
    10: (3, 31, 0),
}

# Master branch URL (latest schema)
MASTER_URL = "https://raw.githubusercontent.com/Kitware/CMake/refs/heads/master/Help/manual/presets/schema.json"
VERSIONED_URL = "https://raw.githubusercontent.com/Kitware/CMake/refs/tags/v{}.{}.{}/Help/manual/presets/schema.json"


def get_schema(version: int) -> dict[str, Any]:
    """
    Get the CMake presets schema that supports the specified version.

    Args:
        version: The schema version number to get.

    Returns:
        The schema as a dictionary.

    Raises:
        SchemaDownloadError: If the schema cannot be downloaded or doesn't support the requested version.
        VersionError: If the schema version is not supported.
    """
    if version <= 1:
        raise VersionError(f"Unsupported schema version: {version}")

    logger.debug(f"Requesting schema for version {version}")

    # First check if we have a cached schema for this version
    cache_dir = Path.home() / ".cache" / "cmakepresets-schema"
    cache_file = cache_dir / f"schema-v{version}.json"

    # Try to load from cache first
    if cache_file.exists():
        try:
            logger.debug(f"Found cached schema at {cache_file}")
            with open(cache_file, encoding="utf-8") as f:
                schema: dict[str, Any] = json.load(f)

            # Check if the cached schema supports the requested version
            if schema_has_version(schema, version):
                logger.debug(f"Cached schema supports version {version}")
                return schema
            else:
                logger.debug(f"Cached schema does not support version {version}, will download")
        except (OSError, json.JSONDecodeError) as e:
            logger.debug(f"Error reading cached schema: {e}")
            # If there's an error reading the cache, we'll just download a new schema
            pass
    else:
        logger.debug(f"No cached schema found for version {version}")

    # Determine the URL to download the schema based on version
    url = get_schema_url_for_version(version)
    logger.info(f"Downloading schema for version {version} from {url}")

    # If it's from master (unknown version), we'll store it differently
    is_master = url == MASTER_URL
    if is_master:
        cache_file = cache_dir / "schema.json"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        schema = response.json()
        logger.debug(f"Successfully downloaded schema from {url}")

        # Check if the downloaded schema supports the requested version
        if not schema_has_version(schema, version) and not is_master:
            logger.error(f"Downloaded schema does not support version {version}")
            raise SchemaDownloadError(f"Downloaded schema does not support version {version}")

        # Save the downloaded schema to the cache
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(schema, f)
        logger.debug(f"Saved schema to cache at {cache_file}")

        logger.info(f"Successfully retrieved schema for version {version}")
        return schema
    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.error(f"Failed to download schema for version {version}: {e}")
        raise SchemaDownloadError(f"Failed to download schema: {e}")


def get_schema_url_for_version(version: int) -> str:
    """
    Determine the correct GitHub URL for the schema based on the requested version.

    Args:
        version: The schema version to get.

    Returns:
        The URL to download the schema from.
    """

    if version in _schema_version_cmake_version:
        cmake_version = _schema_version_cmake_version[version]
        url = VERSIONED_URL.format(*cmake_version)
        logger.debug(f"Using CMake {cmake_version[0]}.{cmake_version[1]}.{cmake_version[2]} schema URL for version {version}")
        return url
    else:
        # For unknown or future versions, use the latest from master
        logger.warning(f"No specific CMake version known for schema version {version}, using latest from master")
        return MASTER_URL


def get_latest_master_schema(force_download: bool = False) -> dict[str, Any]:
    """
    Get the latest schema from the master branch.

    Args:
        force_download: If True, download a fresh copy even if cached version exists.

    Returns:
        The schema as a dictionary.

    Raises:
        SchemaDownloadError: If the schema cannot be downloaded.
    """
    cache_dir = Path.home() / ".cache" / "cmakepresets-schema"
    cache_file = cache_dir / "schema.json"

    if force_download:
        logger.debug("Forcing download of master schema")

    # Use cached version if available and not forcing download
    if not force_download and cache_file.exists():
        try:
            logger.debug(f"Using cached master schema from {cache_file}")
            with open(cache_file, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            logger.debug(f"Error reading cached master schema: {e}")
            # If there's an error reading the cache, we'll download a new one
            pass
    else:
        if not force_download:
            logger.debug("No cached master schema found")

    logger.info("Downloading latest schema from master branch")
    try:
        response = requests.get(MASTER_URL, timeout=10)
        response.raise_for_status()
        schema: dict[str, Any] = response.json()
        logger.debug("Successfully downloaded master schema")

        # Save the downloaded schema to the cache
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(schema, f)
        logger.debug(f"Saved master schema to cache at {cache_file}")

        return schema
    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.error(f"Failed to download master schema: {e}")
        raise SchemaDownloadError(f"Failed to download latest schema: {e}")


def schema_has_version(schema: dict[str, Any], version: int) -> bool:
    """
    Check if a schema supports the specified version.

    Args:
        schema: The schema to check.
        version: The version to look for.

    Returns:
        True if the schema supports the specified version, False otherwise.
    """
    if "oneOf" in schema:
        for variant in schema.get("oneOf", []):
            if "properties" in variant and "version" in variant["properties"]:
                version_property = variant["properties"]["version"]
                if "const" in version_property and version_property["const"] == version:
                    return True
    return False


def validate_json_against_schema(data: dict[str, Any], schema: dict[str, Any]) -> None:
    """
    Validate JSON data against a schema.

    Args:
        data: The JSON data to validate.
        schema: The JSON schema to validate against.

    Raises:
        jsonschema.exceptions.ValidationError: If the data does not validate against the schema.
    """
    doc_version = data.get("version", "unknown")
    logger.debug(f"Validating document with version {doc_version} against schema")

    if _is_version_1(data):
        logger.warning("Document uses unsupported schema version 1")
        raise VersionError("Unsupported schema version: 1")

    try:
        # Handle future versions and attempt validation
        if _is_future_version(data, schema):
            logger.info(f"Document version {doc_version} is newer than schema supports")
            if _try_validate_future_version(data, schema):
                logger.info(f"Successfully validated document with future version {doc_version}")
                return
            logger.warning(f"Could not validate document with version {doc_version} using any available schema")

        # Proceed with normal validation
        jsonschema.validate(data, schema)
        logger.debug("Document successfully validated against schema")
    except jsonschema.exceptions.ValidationError as e:
        # Improve error reporting
        error_message = _get_improved_error_message(data, e)
        if error_message:
            logger.error(f"Validation error: {error_message}")
            raise jsonschema.exceptions.ValidationError(error_message) from e
        error_str = str(e)
        error_lines = error_str.splitlines()
        if len(error_lines) > 10:
            truncated_error = "\n".join(error_lines[:10]) + "\n..."
            logger.error(f"Validation error: {truncated_error}")
        else:
            logger.error(f"Validation error: {e}")
        raise


def _is_version_1(data: dict[str, Any]) -> bool:
    if "version" in data and data["version"] == 1:
        return True
    return False


def _is_future_version(data: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Check if data has a version newer than what's defined in schema."""
    if "oneOf" not in schema or "version" not in data:
        return False

    schema_versions = _get_schema_versions(schema)
    return data["version"] not in schema_versions and data["version"] > max(schema_versions, default=0)


def _get_schema_versions(schema: dict[str, Any]) -> set[int]:
    """Extract all version numbers defined in the schema."""
    schema_versions: set[int] = set()
    for variant in schema.get("oneOf", []):
        if "properties" in variant and "version" in variant["properties"]:
            version_property = variant["properties"]["version"]
            if "const" in version_property and isinstance(version_property["const"], int):
                schema_versions.add(version_property["const"])
    return schema_versions


def _try_validate_future_version(data: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Try to validate a future version against the highest known version in schema."""

    def try_validation_with_schema(schema_to_use: dict[str, Any], description: str) -> bool:
        """Helper to attempt validation with a given schema."""
        schema_versions = _get_schema_versions(schema_to_use)
        if not schema_versions:
            return False

        highest_version = max(schema_versions)
        validation_data = data.copy()
        validation_data["version"] = highest_version

        try:
            logger.warning(f"{description} (version {highest_version})")
            jsonschema.validate(validation_data, schema_to_use)
            return True
        except jsonschema.exceptions.ValidationError:
            return False

    # First try with the provided schema
    original_msg = f"Schema for version {data['version']} not available. Validating against version"
    if try_validation_with_schema(schema, original_msg):
        return True

    try:
        # Try with cached master schema
        master_schema = get_latest_master_schema()
        if try_validation_with_schema(master_schema, "Trying validation against latest cached schema"):
            return True

        # Last attempt with freshly downloaded schema
        master_schema = get_latest_master_schema(force_download=True)
        return try_validation_with_schema(master_schema, "Trying validation against freshly downloaded schema")

    except SchemaDownloadError:
        # If we can't download the schema, just continue with normal validation
        pass

    return False


def _get_feature_min_versions(schema: dict[str, Any]) -> dict[str, int]:
    """Extract the minimum version required for each field in the schema."""
    feature_min_versions = {}

    for variant in schema.get("oneOf", []):
        if "properties" in variant and "version" in variant["properties"]:
            variant_version = variant["properties"]["version"].get("const")
            if variant_version is not None:
                for field_name in variant.get("properties", {}):
                    if field_name != "version":
                        if field_name not in feature_min_versions:
                            feature_min_versions[field_name] = variant_version
                        else:
                            feature_min_versions[field_name] = min(feature_min_versions[field_name], variant_version)

    return feature_min_versions


def _get_improved_error_message(data: dict[str, Any], original_error: jsonschema.exceptions.ValidationError) -> str | None:
    """Generate a more helpful error message for schema validation failures."""
    # Check for version compatibility with specific fields
    if "version" in data:
        version = data["version"]

        # Try to get the latest master schema to provide better field version information
        try:
            master_schema = get_latest_master_schema()
            feature_min_versions = _get_feature_min_versions(master_schema)

            # First check for fields that require newer versions
            for field in data:
                if field in feature_min_versions and version < feature_min_versions[field]:
                    return f"The '{field}' field is first available in version {feature_min_versions[field]} or higher, but document version is {version}"
        except SchemaDownloadError:
            # If we can't download the schema, continue with basic error handling
            logger.debug("Could not download master schema for improved error messages")

    # Create user-friendly messages for common error patterns
    error_message = str(original_error)
    if "is not valid under any of the given schemas" in error_message:
        if "version" in data:
            return f"Schema validation failed for version {data['version']}. Please check that all fields are valid for this version."
        else:
            return "Schema validation failed. The document doesn't match the expected schema."

    return None  # Keep original error message if no improvements made


def check_cmake_version_for_schema(schema_version: int, cmake_min_required: dict[str, int]) -> None:
    """
    Check if the CMake minimum required version is sufficient for the schema version.
    Logs warnings if the CMake version is too low or if the schema version is unknown.

    Args:
        schema_version: The schema version being used.
        cmake_min_required: Dictionary with 'major', 'minor', and 'patch' keys.
    """
    if schema_version not in _schema_version_cmake_version:
        logger.warning(f"Unknown schema version: {schema_version}")
        return

    required_version = _schema_version_cmake_version[schema_version]
    provided_version = (cmake_min_required.get("major", 0), cmake_min_required.get("minor", 0), cmake_min_required.get("patch", 0))

    if provided_version < required_version:
        req_str = f"{required_version[0]}.{required_version[1]}.{required_version[2]}"
        prov_str = f"{provided_version[0]}.{provided_version[1]}.{provided_version[2]}"
        logger.warning(f"Schema version {schema_version} requires CMake {req_str} or higher, but cmakeMinimumRequired is set to {prov_str}")
    else:
        logger.debug(
            f"CMake minimum required version {provided_version[0]}.{provided_version[1]}.{provided_version[2]} "
            f"is sufficient for schema version {schema_version}",
        )
