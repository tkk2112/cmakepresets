import logging
from typing import Any, Final

import jsonschema
from rich.console import Console
from rich.logging import RichHandler

CRITICAL: Final = logging.CRITICAL
ERROR: Final = logging.ERROR
WARNING: Final = logging.WARNING
INFO: Final = logging.INFO
DEBUG: Final = logging.DEBUG
NOTSET: Final = logging.NOTSET


class Logger(logging.Logger):
    """
    Configure rich-based logging for the application.

    Args:
        level: The logging level to use
        colors: Whether to use colors in the console output
    """

    def __init__(self, level: int = WARNING, colors: bool = True):
        super().__init__(name="cmakepresets", level=level)

        self.parent = logging.root

        self.console = Console(color_system="auto" if colors else None)

        handler = RichHandler(console=self.console, rich_tracebacks=True, tracebacks_suppress=[jsonschema])
        formatter = logging.Formatter("[%(name)s]   %(message)s")
        handler.setFormatter(formatter)

        self.addHandler(handler)

    def getChild(self, name: str) -> Any:
        if "cmakepresets" not in name:
            name = f"cmakepresets.{name}"
        child = self.root.manager.getLogger(name)
        child.parent = self
        return child
