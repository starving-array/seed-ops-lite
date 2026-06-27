"""Lightweight, type-safe dependency injection container."""

import inspect
from collections.abc import Callable
from typing import Any, TypeVar, cast

T = TypeVar("T")


class DIContainer:
    """Lightweight dependency injection container.

    Supports singletons, lazy initialization, and async.
    """

    def __init__(self) -> None:
        """Initialize the container."""
        self._providers: dict[type[Any] | str, Callable[..., Any]] = {}
        self._instances: dict[type[Any] | str, Any] = {}
        self._singletons: set[type[Any] | str] = set()

    def register(
        self,
        dependency_type: type[T] | str,
        factory: Callable[..., T] | Callable[..., Any],
        singleton: bool = True,
    ) -> None:
        """Register a dependency provider.

        Args:
            dependency_type: The class type or string key.
            factory: A callable that returns the instance.
            singleton: Whether the instance should be a singleton.
        """
        self._providers[dependency_type] = factory
        if singleton:
            self._singletons.add(dependency_type)
        else:
            self._singletons.discard(dependency_type)
        # Clear cached instance if re-registered
        self._instances.pop(dependency_type, None)

    def get(self, dependency_type: type[T] | str) -> T:
        """Resolve a synchronous dependency.

        Args:
            dependency_type: The class type or string key to resolve.

        Returns:
            T: The resolved dependency instance.

        Raises:
            ValueError: If the dependency is not registered or is asynchronous.
        """
        if dependency_type not in self._providers:
            raise ValueError(f"Dependency {dependency_type} is not registered.")

        if dependency_type in self._instances:
            return cast(T, self._instances[dependency_type])

        factory = self._providers[dependency_type]
        if inspect.iscoroutinefunction(factory):
            raise ValueError(
                f"Dependency {dependency_type} is asynchronous. Use resolve() instead."
            )

        instance = factory()
        if dependency_type in self._singletons:
            self._instances[dependency_type] = instance

        return cast(T, instance)

    async def resolve(self, dependency_type: type[T] | str) -> T:
        """Resolve a dependency (supports both sync and async factories).

        Args:
            dependency_type: The class type or string key to resolve.

        Returns:
            T: The resolved dependency instance.

        Raises:
            ValueError: If the dependency is not registered.
        """
        if dependency_type not in self._providers:
            raise ValueError(f"Dependency {dependency_type} is not registered.")

        if dependency_type in self._instances:
            return cast(T, self._instances[dependency_type])

        factory = self._providers[dependency_type]
        if inspect.iscoroutinefunction(factory):
            instance = await factory()
        else:
            instance = factory()

        if dependency_type in self._singletons:
            self._instances[dependency_type] = instance

        return cast(T, instance)

    def clear(self) -> None:
        """Clear all registered providers and cached instances."""
        self._providers.clear()
        self._instances.clear()
        self._singletons.clear()


# Global DI container instance
container = DIContainer()
