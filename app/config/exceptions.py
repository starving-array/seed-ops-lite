"""Custom exceptions for the Configuration Engine."""


class ConfigurationException(Exception):
    """Base exception for all configuration engine errors."""

    pass


class ConfigurationValidationException(ConfigurationException):
    """Raised when configuration validation fails."""

    pass
