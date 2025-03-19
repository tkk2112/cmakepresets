from typing import Final

import rich

from .log import Logger

logger: Final[Logger] = Logger()
console: Final[rich.console.Console] = logger.console

# Then import other modules that may use the logger
from .exceptions import FileParseError, FileReadError, VersionError  # noqa: E402
from .parser import Parser  # noqa: E402
from .presets import CMakePresets  # noqa: E402

__all__: Final = [
    "logger",
    "console",
    "Parser",
    "CMakePresets",
    "FileReadError",
    "FileParseError",
    "VersionError",
]
__version__ = "v0.3.1"  # {x-release-please-version}
