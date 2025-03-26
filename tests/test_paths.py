from pathlib import Path
from typing import cast

from cmakepresets.constants import CONFIGURE, PRESET_MAP
from cmakepresets.paths import CMakeRoot

from .decorators import CMakePresets_json


@CMakePresets_json()
def test_init_with_file_path() -> None:
    """Test initialization with a file path."""
    root = CMakeRoot("/home/user/project/CMakePresets.json")
    assert root.source_dir == Path("/home/user/project")
    assert root.presets_file == Path("/home/user/project/CMakePresets.json")
    assert root.has_user_presets is False


@CMakePresets_json()
def test_init_with_directory_path() -> None:
    """Test initialization with a directory path."""
    root = CMakeRoot("/home/user/project")
    assert root.source_dir == Path("/home/user/project")
    assert root.presets_file == Path("/home/user/project/CMakePresets.json")
    assert root.has_user_presets is False


@CMakePresets_json(
    {
        "CMakePresets.json": {"version": 4},
        "CMakeUserPresets.json": {"version": 4},
    },
)
def test_user_presets_detection() -> None:
    """Test detection of CMakeUserPresets.json."""
    # Using actual files created by the decorator
    root = CMakeRoot("CMakePresets.json")
    assert root.has_user_presets is True
    assert root.user_presets_file == Path("/home/user/project/CMakeUserPresets.json")


@CMakePresets_json(
    {
        "CMakePresets.json": {"version": 4, "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0}},
        "CMakeUserPresets.json": {"version": 4, PRESET_MAP[CONFIGURE]: [{"name": "user"}]},
    },
)
def test_paths_integration() -> None:
    """Integration test with actual file system (mocked)."""
    root = CMakeRoot("CMakePresets.json")
    assert root.has_user_presets is True
    assert cast(Path, root.presets_file).name == "CMakePresets.json"
    assert cast(Path, root.user_presets_file).name == "CMakeUserPresets.json"


@CMakePresets_json({"fake_file": ""})  # Just to activate the decorator
def test_relative_path_methods() -> None:
    """Test the relative path methods."""
    root = CMakeRoot("/home/user/project")

    # Test get_relative_path
    assert root.get_relative_path(Path("/home/user/project/src/main.cpp")) == "src/main.cpp"
    assert root.get_relative_path(Path("/other/path/file.txt")) == "/other/path/file.txt"


@CMakePresets_json()
def test_missing_file_handling() -> None:
    """Test behavior when trying to initialize with a missing file.
    The decorator adds files to Path.cwd() in fake filesystem,
    so nothing is going to be found at /path/to/project."""

    root = CMakeRoot("/path/to/project")
    assert root.presets_file is None
    assert root.has_presets is False
    assert root.user_presets_file is None
    assert root.has_user_presets is False
