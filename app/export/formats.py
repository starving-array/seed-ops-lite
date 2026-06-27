"""Format serializers for the Export Engine."""

import csv
import io
import json
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.export.exceptions import ExportException


class FormatSerializer(ABC):
    """Abstract base class for formatting and serializing datasets."""

    @abstractmethod
    def serialize(
        self,
        records: dict[str, list[dict[str, Any]]],
        options: dict[str, Any] | None = None,
    ) -> dict[str, bytes]:
        """Serialize the records.

        Args:
            records: Dataset table mappings.
            options: Optional serialization overrides.

        Returns:
            dict[str, bytes]: Map of file/key identifiers to serialized bytes.
        """
        pass


class JSONSerializer(FormatSerializer):
    """Serializes dataset into a unified JSON document."""

    def serialize(
        self,
        records: dict[str, list[dict[str, Any]]],
        options: dict[str, Any] | None = None,
    ) -> dict[str, bytes]:
        """Serialize as a single JSON object.

        Options supported:
            - indent: json indentation level (default: 2)
        """
        options = options or {}
        indent = options.get("indent", 2)
        try:
            # Serialize the whole records dictionary
            json_str = json.dumps(records, indent=indent, default=str)
            return {"dataset.json": json_str.encode("utf-8")}
        except Exception as e:
            raise ExportException(f"Failed to serialize dataset to JSON: {e!s}") from e


class CSVSerializer(FormatSerializer):
    """Serializes dataset tables into individual CSV documents."""

    def serialize(
        self,
        records: dict[str, list[dict[str, Any]]],
        options: dict[str, Any] | None = None,
    ) -> dict[str, bytes]:
        """Serialize each table to a separate CSV byte block.

        Options supported:
            - delimiter: character field delimiter (default: ',')
        """
        options = options or {}
        delimiter = options.get("delimiter", ",")
        serialized_outputs: dict[str, bytes] = {}

        for table_name, rows in records.items():
            if not rows:
                # If table has no rows, export empty CSV with no header (or empty bytes)
                serialized_outputs[f"{table_name}.csv"] = b""
                continue

            try:
                # Use keys of first record as headers
                headers = list(rows[0].keys())
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=headers, delimiter=delimiter)
                writer.writeheader()
                writer.writerows(rows)
                serialized_outputs[f"{table_name}.csv"] = output.getvalue().encode(
                    "utf-8"
                )
            except Exception as e:
                raise ExportException(
                    f"Failed to serialize table '{table_name}' to CSV: {e!s}"
                ) from e

        return serialized_outputs


class SerializerRegistry:
    """Registry pattern keeping track of available export format serializers."""

    _registry: ClassVar[dict[str, type[FormatSerializer]]] = {}

    @classmethod
    def register(cls, format_name: str, serializer_cls: type[FormatSerializer]) -> None:
        """Register a format serializer class."""
        cls._registry[format_name.lower()] = serializer_cls

    @classmethod
    def get(cls, format_name: str) -> FormatSerializer:
        """Instantiate and return the requested format serializer."""
        serializer_cls = cls._registry.get(format_name.lower())
        if not serializer_cls:
            from app.export.exceptions import UnsupportedFormatException

            raise UnsupportedFormatException(
                f"Unsupported export format: '{format_name}'. "
                f"Supported formats: {list(cls._registry.keys())}"
            )
        return serializer_cls()


# Auto-register default formats
SerializerRegistry.register("json", JSONSerializer)
SerializerRegistry.register("csv", CSVSerializer)
