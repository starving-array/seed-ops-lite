"""Custom exception classes for the Skill Framework."""


class SkillError(Exception):
    """Base exception for all skill-related errors."""

    pass


class SkillValidationError(SkillError):
    """Raised when validation of input parameters for a skill fails."""

    pass


class SkillExecutionError(SkillError):
    """Raised when execution of a skill fails at runtime."""

    pass


class SkillNotFoundError(SkillError):
    """Raised when a requested skill is not found in the registry."""

    pass
