import time
from datetime import UTC, datetime

from app.core.version import SCHEMA_HASH_VERSION, VALIDATOR_VERSION
from app.telemetry.events import EventID
from app.telemetry.logger import logger
from app.telemetry.timer import timer
from app.validation.ddl_validator import DDLValidator
from app.validation.hash import extract_enum_definitions, generate_schema_hash
from app.validation.regex_validator import RegexValidator
from app.validation.rules import ValidationRule
from app.validation.security_validator import SecurityValidator
from app.validation.validation_errors import ValidationErrorCode, ValidationErrorDetail
from app.validation.validation_result import (
    ValidationResult,
    ValidationStatistics,
    ValidationSuggestion,
)

TOTAL_RULE_COUNT = 13


class AirlockValidator:
    """Central entry point for deterministic validation of SQL DDL schemas."""

    def __init__(
        self,
        regex_validator: RegexValidator,
        ddl_validator: DDLValidator,
        security_validator: SecurityValidator,
    ) -> None:
        """Initialize AirlockValidator with its dependencies.

        Args:
            regex_validator: Helper for lexical validations.
            ddl_validator: Helper for parsing and semantic validates.
            security_validator: Helper for detecting malicious queries.
        """
        self._regex_validator = regex_validator
        self._ddl_validator = ddl_validator
        self._security_validator = security_validator

    async def validate_schema(self, ddl: str) -> ValidationResult:
        """Validate a SQL DDL schema deterministically.

        Runs security, regex, and semantic DDL validations.

        Args:
            ddl: Raw input SQL DDL string.

        Returns:
            ValidationResult: The validation report including allowed status.
        """
        start_time = time.perf_counter()
        validation_timestamp = datetime.now(UTC).isoformat()

        # Log: Validation Started
        logger.info(
            EventID.LOG_INFO,
            "Validation Started",
            component="AirlockValidator",
        )

        errors: list[ValidationErrorDetail] = []
        warnings: list[str] = []

        with timer("airlock_validation"):
            # 1. Regex validation (lexical, empty checks)
            regex_errors = self._regex_validator.validate(ddl)
            errors.extend(regex_errors)

            if not regex_errors:
                # 2. Security validation (dangerous queries, injection checks)
                security_errors = self._security_validator.validate(ddl)
                errors.extend(security_errors)

                # 3. DDL semantic validation (duplicates, primary keys, foreign keys)
                ddl_errors = self._ddl_validator.validate(ddl)
                errors.extend(ddl_errors)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        success = len(errors) == 0
        execution_allowed = success

        # 4. Generate deterministic schema hash
        enums = extract_enum_definitions(ddl)
        schema_hash = generate_schema_hash(
            ddl, enums, VALIDATOR_VERSION, SCHEMA_HASH_VERSION
        )

        # 5. Extract statistics
        parsed_tables = self._ddl_validator.last_parsed_tables
        table_count = len(parsed_tables)
        column_count = sum(len(tbl.columns) for tbl in parsed_tables.values())

        statistics = ValidationStatistics(
            rule_count=TOTAL_RULE_COUNT,
            table_count=table_count,
            column_count=column_count,
            error_count=len(errors),
            warning_count=len(warnings),
        )

        # 6. Map suggestions with metadata
        suggestions: list[ValidationSuggestion] = []
        if success:
            suggestions.append(
                ValidationSuggestion(
                    rule_id=ValidationRule.GEN_SUCCESS,
                    message="DDL schema is structurally valid and secure.",
                    suggested_fix="No remediation needed. Ready for generation phase.",
                    confidence=1.00,
                )
            )
        else:
            for err in errors:
                warnings.append(
                    f"Blocking error found: {err.message} (Location: {err.location})"
                )

                # Rule-id mapping based on the error code and descriptions
                rule_id = ValidationRule.GEN_SUCCESS
                confidence = 1.00

                if err.code == ValidationErrorCode.EMPTY_SCHEMA:
                    rule_id = ValidationRule.LEX_EMPTY_SCHEMA
                    confidence = 1.00
                elif err.code == ValidationErrorCode.MALFORMED_DDL:
                    if "parenthes" in err.message.lower():
                        rule_id = ValidationRule.LEX_UNMATCHED_PARENTHESIS
                        confidence = 1.00
                    else:
                        rule_id = ValidationRule.LEX_UNMATCHED_QUOTES
                        confidence = 1.00
                elif err.code == ValidationErrorCode.RESERVED_KEYWORD:
                    if "column" in err.message.lower():
                        rule_id = ValidationRule.SEM_RESERVED_KEYWORD
                        confidence = 0.97
                    else:
                        rule_id = ValidationRule.LEX_RESERVED_KEYWORD
                        confidence = 0.97
                elif err.code == ValidationErrorCode.DANGEROUS_SQL:
                    if "comment" in err.message.lower():
                        rule_id = ValidationRule.SEC_SUSPICIOUS_COMMENT
                        confidence = 1.00
                    else:
                        rule_id = ValidationRule.SEC_FORBIDDEN_KEYWORD
                        confidence = 1.00
                elif err.code == ValidationErrorCode.UNSUPPORTED_STATEMENT:
                    rule_id = ValidationRule.SEC_STATEMENT_PREFIX
                    confidence = 0.98
                elif err.code == ValidationErrorCode.DUPLICATE_TABLE:
                    rule_id = ValidationRule.SEM_DUPLICATE_TABLE
                    confidence = 1.00
                elif err.code == ValidationErrorCode.DUPLICATE_COLUMN:
                    rule_id = ValidationRule.SEM_DUPLICATE_COLUMN
                    confidence = 1.00
                elif err.code == ValidationErrorCode.INVALID_PK:
                    rule_id = ValidationRule.SEM_MISSING_PRIMARY_KEY
                    confidence = 1.00
                elif err.code == ValidationErrorCode.INVALID_FK:
                    rule_id = ValidationRule.SEM_INVALID_FOREIGN_KEY
                    confidence = 0.98
                elif err.code == ValidationErrorCode.INVALID_ENUM:
                    rule_id = ValidationRule.SEM_INVALID_ENUM
                    confidence = 0.99

                suggestions.append(
                    ValidationSuggestion(
                        rule_id=rule_id,
                        message=err.message,
                        suggested_fix=err.suggested_fix,
                        confidence=confidence,
                    )
                )

        # Update statistics warning count after suggestions mapping
        statistics.warning_count = len(warnings)

        # 7. Telemetry Logging
        log_fields = {
            "schema_hash": schema_hash,
            "rule_count": TOTAL_RULE_COUNT,
            "table_count": table_count,
            "column_count": column_count,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }

        if success:
            logger.info(
                EventID.LOG_INFO,
                "Validation Completed",
                duration_ms=round(duration_ms, 2),
                component="AirlockValidator",
                **log_fields,
            )
        else:
            logger.error(
                EventID.LOG_ERROR,
                "Validation Failed",
                duration_ms=round(duration_ms, 2),
                component="AirlockValidator",
                **log_fields,
            )

        return ValidationResult(
            success=success,
            validator_version=VALIDATOR_VERSION,
            validation_timestamp=validation_timestamp,
            validation_duration_ms=round(duration_ms, 2),
            schema_hash=schema_hash,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            statistics=statistics,
            validated_schema=ddl.strip(),
            execution_allowed=execution_allowed,
        )
