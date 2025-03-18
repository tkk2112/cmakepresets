import os

import pytest
from pyfakefs.fake_filesystem_unittest import Patcher

from cmakepresets.exceptions import FileParseError, FileReadError, VersionError
from cmakepresets.parser import Parser

from .decorators import CMakePresets_json


def test_parser_initialization() -> None:
    """Test that parser initializes correctly."""
    parser = Parser()
    assert isinstance(parser, Parser)
    assert parser.loaded_files == {}
    assert parser.processed_files == set()


@CMakePresets_json('{"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}}')
def test_parse_file_basic() -> None:
    """Test parsing a basic valid file with version 4."""
    parser = Parser()
    parser.parse_file("CMakePresets.json")
    # One file is loaded (CMakePresets.json); its content is as provided.
    assert len(parser.loaded_files) == 1
    assert list(parser.loaded_files.values())[0] == {"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}}


@CMakePresets_json("{}")
def test_parse_file_missing_version() -> None:
    """Test parsing a file missing the 'version' field raises VersionError."""
    parser = Parser()
    with pytest.raises(VersionError, match="Missing version"):
        parser.parse_file("CMakePresets.json")


@CMakePresets_json('{"version": 1}')
def test_parse_file_version_too_low() -> None:
    """Test parsing a file with version less than 2 raises VersionError."""
    parser = Parser()
    with pytest.raises(VersionError, match="Unsupported version"):
        parser.parse_file("CMakePresets.json")


@CMakePresets_json('{"version": 2, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}}')
def test_parse_file_valid() -> None:
    """Test that a valid file processes without errors."""
    parser = Parser()
    parser.parse_file("CMakePresets.json")
    # Check that the file is marked as processed.
    assert any("CMakePresets.json" in filename for filename in parser.processed_files)


@CMakePresets_json(
    {
        "CMakePresets.json": '{"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}, "include": ["included.json"]}',
        "included.json": '{"version": 4, "configurePresets": [{"name": "included-preset"}]}',
    },
)
def test_parse_file_with_include() -> None:
    """Test parsing a file with includes loads and processes both files."""
    parser = Parser()
    parser.parse_file("CMakePresets.json")

    # Both files should be processed
    assert len(parser.processed_files) == 2
    assert "CMakePresets.json" in parser.processed_files
    assert "included.json" in parser.processed_files

    # Verify both files are loaded
    assert len(parser.loaded_files) == 2
    assert "CMakePresets.json" in parser.loaded_files
    assert "included.json" in parser.loaded_files

    # Verify the content of included.json has been loaded correctly
    assert "configurePresets" in parser.loaded_files["included.json"]
    assert parser.loaded_files["included.json"]["configurePresets"][0]["name"] == "included-preset"


@CMakePresets_json(
    {
        "CMakePresets.json": '{"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}, "include": ["level1/second.json"]}',
        "level1/second.json": '{"version": 4, "include": ["../level2/third.json"]}',
        "level2/third.json": '{"version": 4, "configurePresets": [{"name": "deep-preset"}]}',
    },
)
def test_parse_file_with_multi_level_includes() -> None:
    """Test parsing with multi-level includes resolves paths correctly."""
    parser = Parser()
    parser.parse_file("CMakePresets.json")

    # All three files should be processed
    assert len(parser.processed_files) == 3
    assert "CMakePresets.json" in parser.processed_files
    assert "level1/second.json" in parser.processed_files
    assert "level2/third.json" in parser.processed_files

    # Verify the deep included content is merged
    assert "configurePresets" in parser.loaded_files["level2/third.json"]
    assert parser.loaded_files["level2/third.json"]["configurePresets"][0]["name"] == "deep-preset"


@CMakePresets_json(
    {
        "project/CMakePresets.json": '{"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}, "include": ["configs/dev.json"]}',
        "project/configs/dev.json": '{"version": 4, "configurePresets": [{"name": "dev-preset"}]}',
    },
)
def test_parse_file_with_relative_include_paths() -> None:
    """Test that includes are resolved relative to the file that includes them."""
    parser = Parser()
    parser.parse_file("project/CMakePresets.json")

    # Both files should be processed with correct paths
    assert len(parser.processed_files) == 2

    assert "CMakePresets.json" in parser.processed_files
    assert "configs/dev.json" in parser.processed_files

    # Verify we can find the included content
    assert "configurePresets" in parser.loaded_files["configs/dev.json"]
    assert parser.loaded_files["configs/dev.json"]["configurePresets"][0]["name"] == "dev-preset"


@CMakePresets_json(
    {
        "CMakePresets.json": '{"version": 3, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}, "configurePresets": [{"name": "base-preset"}]}',
        "CMakeUserPresets.json": '{"version": 3, "configurePresets": [{"name": "user-preset"}]}',
    },
)
def test_parse_file_with_user_presets() -> None:
    """Test that CMakeUserPresets.json is automatically loaded when it exists."""
    parser = Parser()
    parser.parse_file("CMakePresets.json")

    # Both files should be processed
    assert len(parser.processed_files) == 2
    assert "CMakePresets.json" in parser.processed_files
    assert "CMakeUserPresets.json" in parser.processed_files

    # Verify both presets are included in the result
    assert "configurePresets" in parser.loaded_files["CMakePresets.json"]
    assert "configurePresets" in parser.loaded_files["CMakeUserPresets.json"]

    assert parser.loaded_files["CMakePresets.json"]["configurePresets"][0]["name"] == "base-preset"
    assert parser.loaded_files["CMakeUserPresets.json"]["configurePresets"][0]["name"] == "user-preset"


@CMakePresets_json({"/tmp/CMakePresets.json": '{"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}}'})
def test_parse_file_with_absolute_path() -> None:
    """Test parsing a file specified with an absolute path."""
    parser = Parser()
    parser.parse_file("/tmp/CMakePresets.json")

    assert len(parser.loaded_files) == 1
    assert list(parser.loaded_files.keys())[0] == "CMakePresets.json"
    assert parser.loaded_files["CMakePresets.json"]["version"] == 4


@CMakePresets_json(
    {
        "CMakePresets.json": '{"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}, "include": ["/tmp/absolute_include.json"]}',
        "/tmp/absolute_include.json": '{"version": 4, "configurePresets": [{"name": "absolute-preset"}]}',
    },
)
def test_parse_file_with_absolute_include_path() -> None:
    """Test parsing a file that includes another file using an absolute path."""
    parser = Parser()
    parser.parse_file("CMakePresets.json")

    # Both files should be processed
    assert len(parser.processed_files) == 2
    assert "CMakePresets.json" in parser.processed_files

    # The absolute path file should be loaded
    # Note: In the fake filesystem, the absolute path might be stored differently
    assert any("/tmp/absolute_include.json" in path for path in parser.processed_files) or any(
        "absolute_include.json" in path for path in parser.processed_files
    )

    # Verify the included content is available
    absolute_include_content = None
    for file_path, content in parser.loaded_files.items():
        if "absolute_include.json" in file_path:
            absolute_include_content = content
            break

    assert absolute_include_content is not None
    assert "configurePresets" in absolute_include_content
    assert absolute_include_content["configurePresets"][0]["name"] == "absolute-preset"


def test_parser_read_file_errors() -> None:
    """Test error handling when reading files"""
    with Patcher() as patcher:
        # Test non-existent file
        parser = Parser()
        with pytest.raises(FileReadError):
            parser.parse_file("nonexistent_file.json")

        # Test permission error
        patcher.fs.create_file("test_no_permission.json", contents="{}")
        os.chmod("test_no_permission.json", 0)
        with pytest.raises(FileReadError):
            parser.parse_file("test_no_permission.json")


def test_parser_invalid_json() -> None:
    """Test handling of invalid JSON"""
    with Patcher() as patcher:
        # Test non-existent file
        parser = Parser()
        patcher.fs.create_file("invalid.json", contents="{invalid json")
        with pytest.raises(FileParseError):
            parser.parse_file("invalid.json")


@CMakePresets_json(
    {
        "CMakePresets.json": '{"version": 4,  "include": ["file1.json"]}',
        "file1.json": '{"version": 4, "include": ["file2.json"]}',
        "file2.json": '{"version": 4, "include": ["file1.json"]}',
    },
)
def test_parser_deals_with_circular_include_detection() -> None:
    """Test detection of circular includes"""
    parser = Parser()
    parser.parse_file("CMakePresets.json")
