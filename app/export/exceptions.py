"""Custom exceptions for the Export Engine."""


class ExportException(Exception):
    """Base exception for all Export Engine errors."""

    pass


class UnsupportedFormatException(ExportException):
    """Raised when the requested export format is not supported or registered."""

    pass


class ExportValidationException(ExportException):
    """Raised when the dataset fails validation checks before export."""

    pass


class ExportWriteException(ExportException):
    """Raised when writing serialized data to disk fails."""

    pass
