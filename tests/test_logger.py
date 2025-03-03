from cmakepresets import console, logger
from cmakepresets.log import DEBUG, Logger


def test_logger_creation() -> None:
    # Test the logger setup function
    test_logger = Logger(level=DEBUG)
    assert test_logger.name == "cmakepresets"

    # Test the pre-configured logger
    assert logger.name == test_logger.name

    # Test creating child loggers
    child_logger = logger.getChild("test")
    assert child_logger.name == "cmakepresets.test"


def test_console_exists() -> None:
    assert console is not None


def test_Console_is_Logger_console() -> None:
    assert logger.console is console
