class CMakePresetsError(Exception):
    """Base exception for all cmakepresets errors."""


class FileReadError(CMakePresetsError):
    """Raised when a file cannot be read."""


class FileParseError(CMakePresetsError):
    """Raised when a file cannot be parsed as JSON."""


class VersionError(CMakePresetsError):
    """Raised when version requirements are not met."""


class SchemaDownloadError(CMakePresetsError):
    """Raised when a schema cannot be downloaded or accessed."""
