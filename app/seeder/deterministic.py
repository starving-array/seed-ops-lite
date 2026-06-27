"""Deterministic data generation strategy."""

import datetime
import random
import uuid
from typing import Any

from app.seeder.models import FieldDefinition
from app.seeder.strategy import BaseStrategy


class SeededRandomProvider:
    """Reusable provider of seeded random generator instances for reproducibility."""

    @staticmethod
    def get_generator(seed: int | None = None) -> random.Random:
        """Get a seeded Random instance or secure SystemRandom instance.

        Args:
            seed: Optional seed value.

        Returns:
            random.Random: A random generator instance.
        """
        if seed is not None:
            return random.Random(seed)  # noqa: S311
        return random.SystemRandom()


class DeterministicStrategy(BaseStrategy):
    """Generates synthetic data using deterministic rules without calling external APIs."""

    def __init__(self, seed: int | None = None) -> None:
        """Initialize DeterministicStrategy.

        Args:
            seed: Optional default seed for the random number generator.
        """
        self._seed = seed
        self._random = SeededRandomProvider.get_generator(seed)

    async def generate(
        self,
        fields: dict[str, FieldDefinition],
        count: int,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Generate deterministic fields.

        Args:
            fields: Map of field names to FieldDefinition.
            count: Number of records to generate.
            **kwargs: Extra arguments, e.g. "seed" to override default seeding.

        Returns:
            list[dict[str, Any]]: List of generated records (dicts).
        """
        records: list[dict[str, Any]] = [{} for _ in range(count)]

        # Determine which random generator to use
        request_seed = kwargs.get("seed")
        rng = SeededRandomProvider.get_generator(request_seed or self._seed)

        for field_name, field_def in fields.items():
            field_type = field_def.type.lower()
            rules = field_def.rules or {}

            if field_type == "uuid":
                # For reproducible UUIDs when a seed is provided, we generate them
                # pseudo-randomly using the state-seeded standard Random.
                for i in range(count):
                    if request_seed is not None or self._seed is not None:
                        records[i][field_name] = str(
                            uuid.UUID(int=rng.getrandbits(128))
                        )
                    else:
                        records[i][field_name] = str(uuid.uuid4())

            elif field_type == "id":
                start = int(rules.get("start", 1))
                step = int(rules.get("step", 1))
                for i in range(count):
                    records[i][field_name] = start + i * step

            elif field_type == "date":
                # Determine start and end datetime
                start_str = rules.get("start_date", "2026-01-01T00:00:00")
                end_str = rules.get("end_date", "2026-12-31T23:59:59")
                date_format = rules.get("format", "%Y-%m-%dT%H:%M:%S")

                try:
                    start_dt = datetime.datetime.fromisoformat(start_str)
                except ValueError:
                    start_dt = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

                try:
                    end_dt = datetime.datetime.fromisoformat(end_str)
                except ValueError:
                    end_dt = datetime.datetime(2026, 12, 31, tzinfo=datetime.UTC)

                # Ensure tzinfo is stripped for calculations if mixed
                if start_dt.tzinfo != end_dt.tzinfo:
                    start_dt = start_dt.replace(tzinfo=None)
                    end_dt = end_dt.replace(tzinfo=None)

                delta_seconds = int((end_dt - start_dt).total_seconds())

                for i in range(count):
                    if delta_seconds > 0:
                        random_seconds = rng.randint(0, delta_seconds)
                        random_dt = start_dt + datetime.timedelta(
                            seconds=random_seconds
                        )
                    else:
                        random_dt = start_dt

                    if date_format == "iso":
                        records[i][field_name] = random_dt.isoformat()
                    else:
                        records[i][field_name] = random_dt.strftime(date_format)

            elif field_type == "boolean":
                true_prob = float(rules.get("true_probability", 0.5))
                for i in range(count):
                    records[i][field_name] = rng.random() < true_prob

            elif field_type == "enum":
                values = rules.get("values", ["active", "inactive"])
                if not values:
                    values = ["active", "inactive"]
                for i in range(count):
                    records[i][field_name] = rng.choice(values)

            elif field_type == "numeric_range":
                min_val = rules.get("min", 0)
                max_val = rules.get("max", 100)
                subtype = rules.get("subtype", "int")

                for i in range(count):
                    if subtype == "float":
                        val_float = rng.uniform(float(min_val), float(max_val))
                        records[i][field_name] = round(
                            val_float, rules.get("precision", 2)
                        )
                    else:
                        records[i][field_name] = rng.randint(int(min_val), int(max_val))

            elif field_type == "rule_based":
                # Rule-based values, e.g., prefix + ID + suffix, or a static default
                prefix = rules.get("prefix", "")
                suffix = rules.get("suffix", "")
                static_value = rules.get("value", None)
                sequential = rules.get("sequential", True)
                start_seq = int(rules.get("start", 1))

                for i in range(count):
                    if static_value is not None:
                        records[i][field_name] = static_value
                    elif sequential:
                        records[i][field_name] = f"{prefix}{start_seq + i}{suffix}"
                    else:
                        rand_num = rng.randint(1000, 9999)
                        records[i][field_name] = f"{prefix}{rand_num}{suffix}"

            else:
                # Fallback for unknown deterministic types
                default_val = rules.get("default", f"deterministic_{field_name}")
                for i in range(count):
                    records[i][field_name] = default_val

        return records
