import json
from pathlib import Path
from typing import Any, Final

from . import logger as mainLogger
from .exceptions import FileParseError, FileReadError, VersionError
from .schema import check_cmake_version_for_schema, get_schema, validate_json_against_schema

logger: Final = mainLogger.getChild(__name__)


class Parser:
    """Parser for CMakePresets.json and related files."""

    def __init__(self) -> None:
        """Initialize the parser."""
        self.loaded_files: dict[str, Any] = {}  # Maps filenames to parsed JSON content
        # Set of already processed files
        self.processed_files: set[str] = set()

    def parse_file(self, filepath: str | Path) -> None:
        """
        Parse a CMakePresets.json file and all included files.

        Args:
            filepath: Path to the CMakePresets.json file

        Raises:
            FileReadError: If the file cannot be read
            FileParseError: If the file cannot be parsed as JSON
            VersionError: If the version is not supported (< 4)
        """
        filepath = Path(filepath).resolve()
        logger.info(f"Starting to parse file: {filepath}")
        self.root_dir = filepath.parent  # store root directory

        # Clear existing data
        self.loaded_files = {}
        self.processed_files = set()

        # Start with the main file using its relative name
        self._load_file(filepath)
        main_rel = filepath.name
        schema_version = self._validate_version_requirements(main_rel, self.loaded_files[main_rel])

        logger.debug(f"Getting schema for version {schema_version}")
        schema = get_schema(schema_version)
        logger.debug(f"Validating main file against schema version {schema_version}")
        validate_json_against_schema(self.loaded_files[main_rel], schema)
        check_cmake_version_for_schema(schema_version, self.loaded_files[main_rel].get("cmakeMinimumRequired", {}))

        # Check if there's a user presets file relative to root_dir
        user_preset_path = self.root_dir / "CMakeUserPresets.json"
        if user_preset_path.exists():
            logger.info(f"Found user preset file: {user_preset_path}")
            self._load_file(user_preset_path)
        else:
            logger.debug("No user preset file found")

        # Process includes recursively (using relative paths)
        logger.debug("Processing includes recursively")
        self._process_includes()

        logger.info(f"Successfully parsed {len(self.loaded_files)} files")

    def _load_file(self, filepath: Path) -> None:
        """
        Load a JSON file into memory.

        Args:
            filepath: Path to the JSON file

        Raises:
            FileReadError: If the file cannot be read
            FileParseError: If the file cannot be parsed as JSON
        """
        logger.debug(f"Loading file: {filepath}")
        try:
            with open(str(filepath), encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            logger.error(f"Failed to read file: {filepath}, error: {e}")
            raise FileReadError(f"Unable to read file {filepath}: {e}")

        try:
            json_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON in file: {filepath}, error: {e}")
            raise FileParseError(f"Unable to parse JSON in {filepath}: {e}")

        # Store file content with key relative to self.root_dir
        try:
            relative_path = str(filepath.relative_to(self.root_dir))
        except ValueError:
            # If the path is not relative to root_dir, use the full path as the key
            relative_path = str(filepath)
            logger.debug(f"Using absolute path as key: {relative_path}")

        self.loaded_files[relative_path] = json_data
        logger.info(f"Successfully loaded file: {filepath}")

    def _validate_version_requirements(self, file_path: str, data: dict[str, Any]) -> int:
        """
        Validate version and cmakeMinimumRequired fields in a CMakePresets file.

        Args:
            file_path: Path to the file being validated
            data: Parsed JSON data from the file

        Returns:
            The schema version number

        Raises:
            VersionError: If version requirements are not met
        """
        # Check version field: must exist and be >= 2
        if "version" not in data:
            logger.error(f"Missing version in {file_path}")
            raise VersionError(f"Missing version in {file_path}; minimum required is 2")

        version: int = data["version"]
        if version < 2:
            logger.error(f"Unsupported version {version} in {file_path}")
            raise VersionError(f"Unsupported version {version} in {file_path}, minimum required is 2")

        logger.debug(f"File {file_path} has valid version: {version}")
        return version

    def _process_includes(self) -> None:
        """
        Process all includes in loaded files recursively.
        """
        files_to_process = list(self.loaded_files.keys())
        logger.debug(f"Starting to process includes for {len(files_to_process)} files")

        while files_to_process:
            current_file = files_to_process.pop(0)

            if current_file in self.processed_files:
                logger.debug(f"Skipping already processed file: {current_file}")
                continue

            current_data = self.loaded_files[current_file]
            # relative directory of current_file
            current_dir = Path(current_file).parent
            logger.debug(f"Processing includes for file: {current_file}")

            # Process includes if present
            if "include" in current_data and isinstance(current_data["include"], list):
                logger.debug(f"Found {len(current_data['include'])} includes in {current_file}")
                for include_path in current_data["include"]:
                    # If include path is relative, resolve it relative to current_dir and then self.root_dir
                    include_abs = (self.root_dir / current_dir / include_path).resolve()
                    try:
                        include_rel = str(include_abs.relative_to(self.root_dir))
                    except ValueError:
                        # If include_abs is not under root_dir, use absolute path as fallback
                        include_rel = str(include_abs)
                        logger.debug(f"Include path {include_path} resolved to outside root_dir: {include_rel}")

                    # Load the file if not already loaded
                    if include_rel not in self.loaded_files:
                        logger.info(f"Including file: {include_rel}")
                        self._load_file(include_abs)
                        files_to_process.append(include_rel)
                    else:
                        logger.debug(f"Include file already loaded: {include_rel}")
            else:
                logger.debug(f"No includes found in {current_file}")

            # Mark file as processed
            self.processed_files.add(current_file)
            logger.debug(f"Marked {current_file} as processed")
