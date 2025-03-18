from typing import Any, cast

import jsonschema
import jsonschema.exceptions
import pytest

from cmakepresets import log, logger
from cmakepresets.exceptions import VersionError
from cmakepresets.schema import check_cmake_version_for_schema, get_schema, validate_json_against_schema


def test_get_schema() -> None:
    def in_schema(version: int, key: str, schema: dict[str, Any]) -> bool:
        if "oneOf" in schema:
            for variant in schema.get("oneOf", []):
                if "properties" in variant and variant["properties"].get("version", {}).get("const") == version and key in variant["properties"]:
                    return True
        return False

    version = 2
    schema = get_schema(version)
    assert in_schema(version, "configurePresets", schema)
    assert in_schema(version, "buildPresets", schema)
    assert in_schema(version, "testPresets", schema)
    assert not in_schema(version, "packagePresets", schema)
    assert not in_schema(version, "workflowPresets", schema)

    version = 6
    schema = get_schema(version)
    assert in_schema(version, "packagePresets", schema)
    assert in_schema(version, "workflowPresets", schema)

    version = 10
    schema = get_schema(version)
    assert in_schema(version, "configurePresets", schema)
    assert in_schema(version, "buildPresets", schema)
    assert in_schema(version, "testPresets", schema)
    assert in_schema(version, "packagePresets", schema)
    assert in_schema(version, "workflowPresets", schema)


def test_schema_getter() -> None:
    with pytest.raises(VersionError):
        get_schema(1)
    # Test that we can get the latest schema even if we don't know what version it belongs to
    get_schema(10000)


def test_validate_json_against_schema() -> None:
    schema_v10 = get_schema(10)

    validate_json_against_schema({"version": 4}, schema_v10)

    with pytest.raises(jsonschema.exceptions.ValidationError, match="'version' is a required property"):
        validate_json_against_schema({}, schema_v10)

    with pytest.raises(VersionError, match="Unsupported schema version: 1"):
        validate_json_against_schema({"version": 1}, schema_v10)

    validate_json_against_schema({"version": 10000}, schema_v10)


def test_validate_include_field_version_compatibility() -> None:
    """Test that using include field with incompatible version gives clear error."""
    schema = get_schema(4)  # Get schema that supports version 4 which allows include field

    valid_data = {"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 20, "patch": 0}, "include": ["included.json"]}
    validate_json_against_schema(valid_data, schema)  # Should not raise

    invalid_data = {"version": 3, "cmakeMinimumRequired": {"major": 3, "minor": 20, "patch": 0}, "include": ["included.json"]}

    with pytest.raises(jsonschema.exceptions.ValidationError) as exc_info:
        validate_json_against_schema(invalid_data, schema)

    assert "include" in str(exc_info.value)
    assert "version 4" in str(exc_info.value)


def test_validate_testpresets_field_version_compatibility() -> None:
    """Test that using testPresets field with incompatible version gives clear error."""
    schema = get_schema(3)  # Get schema that supports version 3

    valid_data = {"version": 3, "cmakeMinimumRequired": {"major": 3, "minor": 20, "patch": 0}, "testPresets": [{"name": "test"}]}
    validate_json_against_schema(valid_data, schema)  # Should not raise

    invalid_data = {"version": 2, "cmakeMinimumRequired": {"major": 3, "minor": 20, "patch": 0}, "include": []}

    with pytest.raises(jsonschema.exceptions.ValidationError, match="The 'include' field is first available in version 4"):
        validate_json_against_schema(invalid_data, schema)


def test_validate_future_version_compatibility(caplog: pytest.LogCaptureFixture) -> None:
    """Test that using a future version is handled gracefully and logs appropriately."""
    logger.setLevel(log.WARNING)

    schema = get_schema(10)  # Latest version we support

    future_data = {
        "version": 11,
        "cmakeMinimumRequired": {"major": 3, "minor": 32, "patch": 0},
    }

    validate_json_against_schema(future_data, schema)

    assert any("version 11" in record.message for record in caplog.records)
    assert any("validating against version" in record.message.lower() for record in caplog.records)


def test_check_cmake_version_for_schema_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Test that warning is logged when schema version requires higher CMake version than provided."""
    logger.setLevel(log.WARNING)

    schema_version = 7
    cmake_min_required = {"major": 3, "minor": 26, "patch": 0}  # Too low for schema version 7

    check_cmake_version_for_schema(schema_version, cmake_min_required)

    assert any("requires CMake 3.27.0" in record.message for record in caplog.records)
    assert any("but cmakeMinimumRequired is set to 3.26.0" in record.message for record in caplog.records)


def test_check_cmake_version_unknown_schema(caplog: pytest.LogCaptureFixture) -> None:
    """Test that warning is logged when schema version is unknown."""
    logger.setLevel(log.WARNING)

    schema_version = 999
    cmake_min_required = {"major": 3, "minor": 30, "patch": 0}

    check_cmake_version_for_schema(schema_version, cmake_min_required)

    assert any("Unknown schema version: 999" in record.message for record in caplog.records)


def test_schema_validation_with_invalid_schema() -> None:
    """Test schema validation with invalid inputs"""
    # Test validating against non-existent schema
    with pytest.raises(jsonschema.exceptions.SchemaError):
        validate_json_against_schema({}, cast(dict[str, Any], {"nonexistent_schema"}))

    # Test with malformed schema
    with pytest.raises(Exception):
        validate_json_against_schema({}, cast(dict[str, Any], {"malformed_schena"}))
