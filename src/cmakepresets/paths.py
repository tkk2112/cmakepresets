from pathlib import Path

from . import logger as mainLogger

logger = mainLogger.getChild(__name__)


class CMakeRoot:
    """Handles path resolution for CMake presets."""

    def __init__(self, path_input: str | Path):
        """
        Initialize with path to CMakePresets.json file or its directory.

        Args:
            path_input: Path to CMakePresets.json file or its directory

        Note:
            If the file doesn't exist, presets_file will be None and has_presets will be False
        """
        path = Path(path_input)

        # Handle relative paths
        if not path.is_absolute():
            path = Path.cwd() / path

        # If it's a file and ends with CMakePresets.json, use its directory
        if str(path).endswith("CMakePresets.json"):
            self._presets_file: Path | None = path
            self._source_dir = path.parent
            logger.debug(f"Using CMakePresets.json file: {self._presets_file}")
        # If it's a directory, look for CMakePresets.json
        else:
            self._source_dir = path
            self._presets_file = path / "CMakePresets.json"
            logger.debug(f"Using directory path: {self._source_dir}")

        if self._presets_file.exists():
            self._has_presets = True
            logger.debug(f"Found presets file: {self._presets_file}")
        else:
            self._has_presets = False
            self._presets_file = None
            logger.debug("No presets file found")

        # Check for user presets - only if we're using a CMakePresets.json file
        if self.has_presets:
            self._user_presets_file: Path | None = self._source_dir / "CMakeUserPresets.json"
            self._has_user_presets = self._user_presets_file.exists()

            if self._has_user_presets:
                logger.debug(f"Found user presets file: {self._user_presets_file}")
            else:
                logger.debug("No user presets file found")
        else:
            self._user_presets_file = None
            self._has_user_presets = False

    @property
    def source_dir(self) -> Path:
        """Get the source directory."""
        return self._source_dir

    @property
    def presets_file(self) -> Path | None:
        """Get the CMakePresets.json file path."""
        return self._presets_file

    @property
    def has_presets(self) -> bool:
        """Check if CMakePresets.json exists."""
        return self._has_presets

    @property
    def user_presets_file(self) -> Path | None:
        """Get the CMakeUserPresets.json file path if it exists, None otherwise."""
        return self._user_presets_file if self._has_user_presets else None

    @property
    def has_user_presets(self) -> bool:
        """Check if CMakeUserPresets.json exists."""
        return self._has_user_presets

    def get_relative_path(self, path: Path) -> str:
        """Return path relative to source directory if possible, otherwise absolute path."""
        try:
            relative = path.relative_to(self._source_dir)
            # Handle the case where path equals source_dir, which would return '.'
            if str(relative) == ".":
                if path.is_file():
                    return path.name
            return str(relative)
        except ValueError:
            return str(path)
