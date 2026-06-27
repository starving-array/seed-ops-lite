"""Data validation engine for generated synthetic records."""

import datetime
import re
import uuid
from typing import Any

from app.seeder.models import FieldDefinition


class SeederValidator:
    """Validator to ensure all generated records adhere to the specifications."""

    @staticmethod
    def validate_record(
        record_data: dict[str, Any], fields: dict[str, FieldDefinition]
    ) -> list[str]:
        """Validate a single record against the requested fields schema.

        Args:
            record_data: The dictionary containing generated field values.
            fields: The schema field definitions.

        Returns:
            list[str]: List of validation error messages.
        """
        errors = []

        for field_name, field_def in fields.items():
            # 1. Required Check
            if field_name not in record_data or record_data[field_name] is None:
                if field_def.required:
                    errors.append(
                        f"Field '{field_name}' is required but was missing or null."
                    )
                continue

            value = record_data[field_name]
            field_type = field_def.type.lower()
            rules = field_def.rules or {}

            # 2. Type and rule validation
            if field_type == "uuid":
                try:
                    uuid.UUID(str(value))
                except ValueError:
                    errors.append(
                        f"Field '{field_name}' value '{value}' is not a valid UUID."
                    )

            elif field_type == "id":
                if not isinstance(value, int):
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        errors.append(
                            f"Field '{field_name}' value '{value}' is not a valid integer ID."
                        )

            elif field_type == "date":
                date_format = rules.get("format", "%Y-%m-%dT%H:%M:%S")
                if date_format == "iso":
                    try:
                        datetime.datetime.fromisoformat(str(value))
                    except ValueError:
                        errors.append(
                            f"Field '{field_name}' value '{value}' is not a valid ISO 8601 date string."
                        )
                else:
                    try:
                        datetime.datetime.strptime(str(value), date_format)
                    except ValueError:
                        errors.append(
                            f"Field '{field_name}' value '{value}' does not match format '{date_format}'."
                        )

            elif field_type == "boolean":
                if not isinstance(value, bool) and str(value).lower() not in [
                    "true",
                    "false",
                    "1",
                    "0",
                ]:
                    errors.append(
                        f"Field '{field_name}' value '{value}' is not a valid boolean."
                    )

            elif field_type == "enum":
                allowed_values = rules.get("values", [])
                if allowed_values and value not in allowed_values:
                    errors.append(
                        f"Field '{field_name}' value '{value}' is not in allowed enum values {allowed_values}."
                    )

            elif field_type == "numeric_range":
                try:
                    num_val = float(value)
                    min_val = rules.get("min")
                    max_val = rules.get("max")
                    if min_val is not None and num_val < float(min_val):
                        errors.append(
                            f"Field '{field_name}' value {num_val} is less than minimum {min_val}."
                        )
                    if max_val is not None and num_val > float(max_val):
                        errors.append(
                            f"Field '{field_name}' value {num_val} is greater than maximum {max_val}."
                        )
                except (ValueError, TypeError):
                    errors.append(
                        f"Field '{field_name}' value '{value}' is not a valid number."
                    )

            elif field_type == "rule_based":
                pattern = rules.get("pattern")
                if pattern:
                    try:
                        if not re.match(pattern, str(value)):
                            errors.append(
                                f"Field '{field_name}' value '{value}' does not match pattern '{pattern}'."
                            )
                    except re.error:
                        pass

            # AI semantic types
            elif field_type in [
                "name",
                "address",
                "biography",
                "description",
                "free_text",
                "domain_content",
            ]:
                if not isinstance(value, str):
                    errors.append(
                        f"Field '{field_name}' value must be a string (got {type(value).__name__})."
                    )
                elif not value.strip():
                    errors.append(
                        f"Field '{field_name}' value must be a non-empty string."
                    )
                else:
                    min_len = rules.get("min_length")
                    max_len = rules.get("max_length")
                    if min_len is not None and len(value) < int(min_len):
                        errors.append(
                            f"Field '{field_name}' length {len(value)} is less than min_length {min_len}."
                        )
                    if max_len is not None and len(value) > int(max_len):
                        errors.append(
                            f"Field '{field_name}' length {len(value)} is greater than max_length {max_len}."
                        )

        return errors
