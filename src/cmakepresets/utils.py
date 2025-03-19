from pathlib import Path


def read_file_text(filepath: Path) -> str:
    """Read and return the text content of the given file."""
    return filepath.read_text(encoding="utf-8")


def write_file_text(filepath: Path, content: str) -> None:
    """Write the given content to the file."""
    filepath.write_text(content, encoding="utf-8")


def get_relative_path(root: Path, filepath: Path) -> str:
    """Return the path of `filepath` relative to root, or absolute if not possible."""
    try:
        return str(filepath.relative_to(root))
    except ValueError:
        return str(filepath)
