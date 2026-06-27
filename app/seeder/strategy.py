"""Base strategy class and registry for synthetic data generation."""

from abc import ABC, abstractmethod
from typing import Any

from app.seeder.models import FieldDefinition, GenerationStrategy


class StrategyRegistry:
    """Registry mapping field types to their corresponding generation strategy classifications."""

    def __init__(self) -> None:
        self._registry: dict[str, GenerationStrategy] = {}
        # Register default mappings
        self.register_deterministic_types(
            ["uuid", "id", "date", "boolean", "enum", "numeric_range", "rule_based"]
        )
        self.register_ai_types(
            [
                "name",
                "address",
                "biography",
                "description",
                "free_text",
                "domain_content",
            ]
        )

    def register(self, field_type: str, strategy: GenerationStrategy) -> None:
        """Register a strategy classification for a given field type."""
        self._registry[field_type.lower()] = strategy

    def register_deterministic_types(self, field_types: list[str]) -> None:
        """Helper to register multiple types to the deterministic strategy."""
        for ft in field_types:
            self.register(ft, GenerationStrategy.DETERMINISTIC)

    def register_ai_types(self, field_types: list[str]) -> None:
        """Helper to register multiple types to the AI strategy."""
        for ft in field_types:
            self.register(ft, GenerationStrategy.AI)

    def get_strategy(self, field_type: str) -> GenerationStrategy | None:
        """Look up the strategy classification for a field type."""
        return self._registry.get(field_type.lower())


# Global strategy registry instance
strategy_registry = StrategyRegistry()


class BaseStrategy(ABC):
    """Abstract base class for data generation strategies."""

    @abstractmethod
    async def generate(
        self,
        fields: dict[str, FieldDefinition],
        count: int,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Generate synthetic records for the specified fields and count.

        Args:
            fields: A dictionary mapping field names to their FieldDefinition.
            count: Number of records to generate.
            **kwargs: Dynamic keyword arguments (e.g. gateway, target context).

        Returns:
            list[dict[str, Any]]: A list of generated field-value dictionaries.
        """
        pass
