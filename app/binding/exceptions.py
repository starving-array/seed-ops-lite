"""Custom exceptions for the Binding Engine."""


class BindingException(Exception):
    """Base exception for all Binding Engine errors."""

    pass


class DependencyResolutionException(BindingException):
    """Raised when dependencies or topological ordering cannot be resolved."""

    pass


class ValidationException(BindingException):
    """Raised when referential validation fails."""

    pass
