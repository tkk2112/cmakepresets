from cmakepresets import __name__, console, logger
from cmakepresets.log import DEBUG, ERROR, Logger


def test_logger_creation() -> None:
    # Test the logger setup function
    test_logger = Logger(level=DEBUG)
    assert test_logger.name == __name__

    # Test the pre-configured logger
    assert logger.name == test_logger.name

    # Test creating child loggers
    child_logger = logger.getChild("module")
    assert child_logger.name == f"{__name__}.module"


def test_console_exists() -> None:
    assert console is not None


def test_Console_is_Logger_console() -> None:
    assert logger.console is console


def test_logger_level_setting() -> None:
    """Test that logger level can be set correctly."""
    # Test setting to different levels
    test_logger = Logger(level=DEBUG)
    assert test_logger.level == DEBUG

    test_logger.setLevel(ERROR)
    assert test_logger.level == ERROR

    # Test that child loggers inherit parent level
    child_logger = test_logger.getChild("child")
    assert child_logger.getEffectiveLevel() == ERROR
