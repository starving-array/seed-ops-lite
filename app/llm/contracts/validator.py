"""Pydantic schema validation engine verifying structural compliance."""

from typing import Any

from pydantic import ValidationError

from app.llm.contracts.base import T
from app.llm.contracts.exceptions import AIContractValidationError


def validate_schema(data: dict[str, Any], schema_cls: type[T]) -> T:
    """Validate a parsed dictionary against a target Pydantic schema.

    Args:
        data: The parsed dictionary representing JSON data.
        schema_cls: The Pydantic model class to validate against.

    Returns:
        T: The instantiated and validated Pydantic model.

    Raises:
        AIContractValidationError: If validation fails or fields are missing/malformed.
    """
    try:
        return schema_cls.model_validate(data)
    except ValidationError as exc:
        # Standardize the validation error list
        errors = [dict(err) for err in exc.errors(include_url=False)]
        raise AIContractValidationError(
            f"Validation failed for schema {schema_cls.__name__}", errors=errors
        ) from exc
