import functools
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

from pyfakefs.fake_filesystem_unittest import Patcher

F = TypeVar("F", bound=Callable[..., Any])


class CMakePresets_json:
    """
    Decorator to set up a fake filesystem with CMakePresets.json files for testing.

    Args:
        content: Either a JSON string to use as the content of CMakePresets.json,
                or a dict mapping filenames to their JSON content strings.
    """

    def __init__(self, content: str | dict[str, str]) -> None:
        self.content = content

    def __call__(self, test_function: F) -> F:
        @functools.wraps(test_function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with Patcher() as patcher:
                fs = patcher.fs

                # Handle the case when content is a single JSON string (for CMakePresets.json)
                if isinstance(self.content, str):
                    self._create_file(fs, "CMakePresets.json", self.content)
                # Handle the case when content is a dict mapping filenames to JSON strings
                elif isinstance(self.content, dict):
                    for filename, file_content in self.content.items():
                        self._create_file(fs, filename, file_content)

                # Run the test function
                return test_function(*args, **kwargs)

        return cast(F, wrapper)

    def _create_file(self, fs: Any, filepath: str, content: str) -> None:
        """
        Create a file in the fake filesystem, creating parent directories as needed.

        Args:
            fs: The fake filesystem
            filepath: Path to the file to create (relative or absolute)
            content: Content to write to the file
        """
        path = Path(filepath)

        # Make sure parent directories exist
        if path.parent != Path(".") and path.parent != Path("/"):
            os.makedirs(path.parent, exist_ok=True)

        # Parse the content to ensure it's valid JSON
        try:
            if not content.strip():
                json_content = {}
            else:
                json_content = json.loads(content)

            # Format the JSON properly for consistent testing
            formatted_content = json.dumps(json_content, indent=2)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in test content for {filepath}: {e}")

        # Create the file
        fs.create_file(filepath, contents=formatted_content)
