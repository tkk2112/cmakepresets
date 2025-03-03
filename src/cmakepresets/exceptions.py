class CMakePresetsError(Exception):
    """Base exception for all cmakepresets errors."""

    pass


class FileReadError(CMakePresetsError):
    """Raised when a file cannot be read."""

    pass


class FileParseError(CMakePresetsError):
    """Raised when a file cannot be parsed as JSON."""

    pass


class VersionError(CMakePresetsError):
    """Raised when version requirements are not met."""

    pass


class SchemaDownloadError(CMakePresetsError):
    """Raised when a schema cannot be downloaded or accessed."""

    pass
