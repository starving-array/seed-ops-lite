"""Custom exceptions for the Hybrid Seeder."""


class SeederException(Exception):
    """Base exception for all Hybrid Seeder operations."""

    pass


class StrategySelectionException(SeederException):
    """Raised when an appropriate generation strategy cannot be selected or is invalid."""

    pass


class GenerationException(SeederException):
    """Raised when record generation fails."""

    pass


class ValidationException(SeederException):
    """Raised when generated synthetic records fail validation checks."""

    pass
