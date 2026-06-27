"""Proxy for core/redis.py backward compatibility."""

from app.core.lifecycle.redis import RedisManager, redis_manager

__all__ = ["RedisManager", "redis_manager"]
