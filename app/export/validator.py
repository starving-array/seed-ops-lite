"""Export validation verifying dataset completeness, schema consistency, and compatibility."""

import os
from pathlib import Path
from typing import Any


class ExportValidator:
    """Validates the readiness of datasets for serialization."""

    def validate(
        self,
        records: dict[str, list[dict[str, Any]]],
        format_name: str,
        target_directory: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> list[str]:
        """Verify dataset completeness, schema consistency, and export compatibility.

        Args:
            records: Dict of table names to lists of record dicts.
            format_name: Name of export format (e.g., 'json', 'csv').
            target_directory: Directory where files will be written.
            options: Optional format serialization parameters.

        Returns:
            list[str]: Validation error messages. Empty list if validation passes.
        """
        errors: list[str] = []

        # 1. Dataset Completeness
        if not isinstance(records, dict):
            errors.append("Export dataset must be a dictionary.")
            return errors

        if not records:
            errors.append("Export dataset is empty: no tables found.")

        # 2. Schema Consistency
        for table_name, rows in records.items():
            if not isinstance(rows, list):
                errors.append(
                    f"Table '{table_name}' records must be a list of dictionaries."
                )
                continue

            if not rows:
                # Empty tables are acceptable, but we should make sure they are not None.
                continue

            # Check that every record in this table is a dictionary and has the same columns (keys)
            first_rec = rows[0]
            if not isinstance(first_rec, dict):
                errors.append(f"Records in table '{table_name}' must be dictionaries.")
                continue

            expected_columns = set(first_rec.keys())
            if not expected_columns:
                errors.append(f"Table '{table_name}' first record has no columns.")

            for idx, row in enumerate(rows):
                if not isinstance(row, dict):
                    errors.append(
                        f"Record at index {idx} in table '{table_name}' is not a dictionary."
                    )
                    continue
                row_columns = set(row.keys())
                if row_columns != expected_columns:
                    errors.append(
                        f"Schema inconsistency in table '{table_name}' at record index {idx}: "
                        f"Expected columns {list(expected_columns)}, but got {list(row_columns)}."
                    )

        # 3. Format/Export Compatibility
        format_lower = format_name.lower()
        if format_lower == "csv":
            # For CSV, values shouldn't be complex nested structures
            for table_name, rows in records.items():
                if not isinstance(rows, list):
                    continue
                for idx, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    for col_name, val in row.items():
                        if col_name == "_lineage":
                            continue
                        if isinstance(val, dict | list | set | tuple):
                            errors.append(
                                f"Export compatibility violation: Table '{table_name}' record index {idx} "
                                f"contains nested structure in column '{col_name}' which is incompatible with CSV."
                            )

            # Validate CSV options
            if options:
                delimiter = options.get("delimiter", ",")
                if not isinstance(delimiter, str) or len(delimiter) != 1:
                    errors.append(
                        f"Export compatibility violation: CSV delimiter must be a single character string. Got: {delimiter}"
                    )

        elif format_lower == "json":
            # Validate JSON options
            if options:
                indent = options.get("indent", 2)
                if indent is not None and not isinstance(indent, int):
                    errors.append(
                        f"Export compatibility violation: JSON indent must be an integer. Got: {indent}"
                    )

        # 4. Target Directory Compatibility (if provided)
        if target_directory:
            target_path = Path(target_directory)
            if target_path.exists():
                if not target_path.is_dir():
                    errors.append(
                        f"Export compatibility violation: Target path '{target_directory}' is a file, not a directory."
                    )
                elif not os.access(target_path, os.W_OK):
                    errors.append(
                        f"Export compatibility violation: Target directory '{target_directory}' is not writable."
                    )
            else:
                # Test if we can create it
                parent_dir = target_path.resolve().parent
                if parent_dir.exists() and not os.access(parent_dir, os.W_OK):
                    errors.append(
                        f"Export compatibility violation: Parent directory '{parent_dir}' is not writable, "
                        f"cannot create target directory '{target_directory}'."
                    )

        return errors
