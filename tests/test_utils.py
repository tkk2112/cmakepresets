from pathlib import Path

import pytest

from cmakepresets.utils import read_file_text, write_file_text


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
