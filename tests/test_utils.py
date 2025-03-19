from pathlib import Path

import pytest

from cmakepresets.utils import get_relative_path, read_file_text, write_file_text


def test_read_write_file_text(tmp_path: Path) -> None:
    """Test read_file_text and write_file_text functions."""
    test_file = tmp_path / "test.txt"
    test_content = "Hello, world!"

    # Test write_file_text
    write_file_text(test_file, test_content)
    assert test_file.exists()

    # Test read_file_text
    content = read_file_text(test_file)
    assert content == test_content

    # Test with non-existent file should raise
    with pytest.raises(FileNotFoundError):
        read_file_text(tmp_path / "nonexistent.txt")


def test_get_relative_path() -> None:
    """Test get_relative_path function."""
    # Create Path objects
    root = Path("/home/user/project")
    file_inside = Path("/home/user/project/src/file.py")
    file_outside = Path("/tmp/file.py")

    # File inside root directory
    rel_path = get_relative_path(root, file_inside)
    assert rel_path == "src/file.py"

    # File outside root directory
    abs_path = get_relative_path(root, file_outside)
    assert abs_path == "/tmp/file.py"

    # Using the same file as root and path
    same_path = get_relative_path(root, root)
    assert same_path == "."
