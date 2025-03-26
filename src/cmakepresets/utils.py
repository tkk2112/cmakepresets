from pathlib import Path


def read_file_text(filepath: Path) -> str:
    """Read and return the text content of the given file."""
    return filepath.read_text(encoding="utf-8")


def write_file_text(filepath: Path, content: str) -> None:
    """Write the given content to the file."""
    filepath.write_text(content, encoding="utf-8")
