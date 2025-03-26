import functools
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast, overload
from unittest.mock import patch

from pyfakefs.fake_filesystem_unittest import Patcher

F = TypeVar("F", bound=Callable[..., Any])


class CMakePresets_json:
    """
    Decorator or context manager to set up a fake filesystem with CMakePresets.json files for testing.

    Can be used as:
    1. A decorator: @CMakePresets_json(content)
    2. A context manager: with CMakePresets_json(content) as fs:

    Args:
        content: Either a JSON string, Python dict to convert to JSON, or
                a dict mapping filenames to JSON content (strings or dicts).
        mock_cwd: The directory to use as the current working directory (default: "/home/user/project")
    """

    @overload
    def __init__(self, content: str, mock_cwd: str = "/home/user/project") -> None: ...

    @overload
    def __init__(self, content: dict[str, Any] = {}, mock_cwd: str = "/home/user/project") -> None: ...

    def __init__(self, content: str | dict[str, Any] = {}, mock_cwd: str = "/home/user/project") -> None:
        self.content = content
        self.mock_cwd = mock_cwd
        self.patcher = None
        self.getcwd_patch = None
        self.pathcwd_patch = None

    def __call__(self, test_function: F) -> F:
        @functools.wraps(test_function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with Patcher() as patcher:
                fs = patcher.fs
                self._setup_files(fs)

                # Patch os.getcwd and Path.cwd to return consistent path
                with patch("os.getcwd", return_value=self.mock_cwd), patch("pathlib.Path.cwd", return_value=Path(self.mock_cwd)):
                    # Run the test function
                    return test_function(*args, **kwargs)

        return cast(F, wrapper)

    def __enter__(self) -> Any:
        """Allow using this as a context manager."""
        self.patcher = Patcher()
        # The patcher is definitely not None at this point
        assert self.patcher is not None
        self.patcher.__enter__()
        fs = self.patcher.fs
        self._setup_files(fs)

        # Patch os.getcwd and Path.cwd
        self.getcwd_patch = patch("os.getcwd", return_value=self.mock_cwd)
        self.pathcwd_patch = patch("pathlib.Path.cwd", return_value=Path(self.mock_cwd))
        self.getcwd_patch.start()
        self.pathcwd_patch.start()

        return fs

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        """Exit the context manager."""
        if self.getcwd_patch:
            self.getcwd_patch.stop()
        if self.pathcwd_patch:
            self.pathcwd_patch.stop()
        if self.patcher:
            self.patcher.__exit__(exc_type, exc_val, exc_tb)
            self.patcher = None

    def _setup_files(self, fs: Any) -> None:
        """Set up all files in the fake filesystem."""
        # Create the mock working directory in the filesystem
        if not fs.exists(self.mock_cwd):
            fs.create_dir(self.mock_cwd)

        # Case 1: Content is a string (JSON content for CMakePresets.json)
        if isinstance(self.content, str):
            self._create_file(fs, "CMakePresets.json", self.content)
            return

        # Case 2: Content is a dictionary that represents a single JSON object
        if isinstance(self.content, dict):
            # Check if this dict appears to be a mapping of filenames to content
            # It's a file mapping if values are strings or dicts
            is_file_mapping = False

            for key, value in self.content.items():
                # If any key seems like a filepath with extension or directory separator
                if isinstance(key, str) and ("." in key or "/" in key or "\\" in key):
                    is_file_mapping = True
                    break

            # If it's not a file mapping, treat the whole dict as CMakePresets.json content
            if not is_file_mapping:
                self._create_file(fs, "CMakePresets.json", json.dumps(self.content))
                return

            # Case 3: Content is a dictionary mapping filenames to content
            for filename, file_content in self.content.items():
                if isinstance(file_content, dict):
                    file_content_str = json.dumps(file_content)
                elif not isinstance(file_content, str):
                    file_content_str = json.dumps(file_content)
                else:
                    file_content_str = file_content

                self._create_file(fs, filename, file_content_str)

    def _create_file(self, fs: Any, filepath: str, content: str) -> None:
        """
        Create a file in the fake filesystem, creating parent directories as needed.

        Args:
            fs: The fake filesystem
            filepath: Path to the file to create (relative or absolute)
            content: Content to write to the file
        """
        # If path is not absolute, make it relative to the mock working directory
        if not Path(filepath).is_absolute():
            filepath = os.path.join(self.mock_cwd, filepath)

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
