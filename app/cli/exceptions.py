"""Custom exceptions for the SeedOps CLI."""


class CLIException(Exception):
    """Base exception for all CLI errors."""

    pass


class CLICommandError(CLIException):
    """Raised when a specific CLI command execution fails."""

    pass


class CLIArgumentError(CLIException):
    """Raised when command-line arguments are invalid or missing."""

    pass
