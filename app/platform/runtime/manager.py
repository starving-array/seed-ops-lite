import asyncio
import builtins
import contextlib
import datetime
from typing import Any

from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.platform.providers.memory import MemoryRuntimeProvider
from app.platform.providers.redis import RedisRuntimeProvider
from app.platform.providers.sqlite import DomainEventDispatcher
from app.platform.runtime.interfaces import RuntimeProvider
from app.telemetry.events import EventID


class RuntimeManager(RuntimeProvider):
    """Orchestrates runtime caching, fallback switches, and automatic recovery protocols."""

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        old_mode = getattr(self, "_mode", "memory")
        self._mode = value
        if old_mode != value:
            logger.info(
                EventID.LOG_INFO,
                f"Runtime mode transition: {old_mode.upper()} -> {value.upper()}",
            )

    @property
    def breaker_state(self) -> str:
        return self._breaker_state

    @breaker_state.setter
    def breaker_state(self, value: str) -> None:
        old_state = getattr(self, "_breaker_state", "CLOSED")
        self._breaker_state = value
        if old_state != value:
            logger.info(
                EventID.LOG_INFO,
                f"Circuit breaker state transition: {old_state} -> {value}",
            )

    def __init__(self) -> None:
        self.redis_provider = RedisRuntimeProvider()
        self.memory_provider = MemoryRuntimeProvider()
        self.active_provider: RuntimeProvider = self.memory_provider
        self._mode = "memory"  # 'redis' | 'memory'
        self.reconnect_count = 0
        self.last_reconnection_time: str | None = None
        self.is_monitoring = False
        self._monitor_task: asyncio.Task[None] | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._sync_queue: asyncio.Queue[str] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._breaker_state = "CLOSED"
        self.last_failure_time: str | None = None
        self.last_recovery_time: str | None = None
        self.failure_count = 0
        self._probe_lock = asyncio.Lock()
        self.dropped_events = 0
        self._pending_keys: dict[str, tuple[str, str, Any]] = {}
        self.coalesced_events = 0
        self.unique_events = 0
        self.skipped_events = 0
        self._worker_start_time: float | None = None
        self._total_sync_time = 0.0
        self._total_sync_count = 0
        self._queue_timestamps: dict[str, float] = {}
        self._last_crossed_threshold = 0

    @property
    def worker_uptime(self) -> float:
        if (
            self._worker_task is not None
            and not self._worker_task.done()
            and self._worker_start_time is not None
        ):
            import time

            return time.time() - self._worker_start_time
        return 0.0

    @property
    def average_sync_time(self) -> float:
        if self._total_sync_count > 0:
            return self._total_sync_time / self._total_sync_count
        return 0.0

    async def initialize(self) -> None:
        """Initialize connection checks and select initial active provider."""
        from app.core.lifecycle.redis import redis_manager

        if self._sync_queue is None:
            self._sync_queue = asyncio.Queue(
                maxsize=platform_settings.RUNTIME_CACHE_SYNC_QUEUE_SIZE
            )

        if self._worker_task is not None and not self._worker_task.done():
            logger.warning(
                EventID.LOG_WARNING,
                "Sync worker is already running. Skipping startup duplication.",
            )
        else:
            import time

            self._worker_start_time = time.time()
            self._worker_task = asyncio.create_task(self._process_sync_queue())

        try:
            # Best-effort connect: if Redis is unreachable, connect() raises but
            # we still attempt ping() through the provider to decide mode.
            with contextlib.suppress(Exception):
                if redis_manager._pool is None:
                    await redis_manager.connect()

            if await self.redis_provider.ping():
                self.active_provider = self.redis_provider
                self.mode = "redis"
                self.breaker_state = "CLOSED"
                DomainEventDispatcher.dispatch("RuntimeStarted", {"provider": "redis"})
                DomainEventDispatcher.dispatch("RedisConnected", {})
                logger.info(
                    EventID.LOG_INFO,
                    "Runtime platform started in REDIS mode.",
                )
                return
        except Exception as e:
            logger.debug(
                EventID.LOG_INFO,
                "Initial Redis ping failed. Fallback mode will activate.",
                error=str(e),
            )

        self.active_provider = self.memory_provider
        self.mode = "memory"
        self.breaker_state = "OPEN"
        self.failure_count += 1
        self.last_failure_time = datetime.datetime.utcnow().isoformat() + "Z"
        DomainEventDispatcher.dispatch("RuntimeStarted", {"provider": "memory"})
        DomainEventDispatcher.dispatch(
            "RuntimeFallbackActivated", {"reason": "Initial connection failed"}
        )
        logger.warning(
            EventID.LOG_WARNING,
            "Failed to connect to Redis. Runtime fallback activated using in-memory mode.",
        )
        self.start_recovery_monitor()

    async def close(self) -> None:
        """Clean shutdown and cancel background monitoring tasks."""
        import time

        shutdown_start = time.time()

        remaining_queued = len(self._pending_keys) if self._pending_keys else 0

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.wait_for(
                    self._monitor_task,
                    timeout=platform_settings.RUNTIME_WORKER_SHUTDOWN_TIMEOUT_SECONDS,
                )
        self._monitor_task = None
        self.is_monitoring = False

        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.wait_for(
                    self._worker_task,
                    timeout=platform_settings.RUNTIME_WORKER_SHUTDOWN_TIMEOUT_SECONDS,
                )
        self._worker_task = None
        self._worker_start_time = None

        shutdown_duration = time.time() - shutdown_start

        DomainEventDispatcher.dispatch("RuntimeStopped", {})
        logger.info(
            EventID.LOG_INFO,
            "Runtime platform stopped. Shutdown summary logged.",
            details={
                "remaining_queued_events": remaining_queued,
                "dropped_events": self.dropped_events,
                "worker_shutdown_duration_seconds": shutdown_duration,
            },
        )

    def start_recovery_monitor(self) -> None:
        """Start the background poll recovery loop if not already running."""
        if not platform_settings.RUNTIME_MEMORY_FALLBACK_ENABLED:
            return
        if self._monitor_task is not None and not self._monitor_task.done():
            self.is_monitoring = True
            return
        self.is_monitoring = True
        logger.info(EventID.LOG_INFO, "Recovery monitor started.")
        self._monitor_task = asyncio.create_task(self._poll_redis_recovery())

    async def _poll_redis_recovery(self) -> None:
        """Periodically check Redis availability to restore primary state."""
        # Initial sleep for the circuit breaker recovery cooldown
        cooldown = platform_settings.RUNTIME_CIRCUIT_BREAKER_RECOVERY_SECONDS
        if cooldown > 0:
            await asyncio.sleep(cooldown)

        interval = platform_settings.RUNTIME_RECOVERY_POLL_INTERVAL_SECONDS
        if platform_settings.RUNTIME_RECONNECT_INTERVAL_SECONDS != 5.0:
            interval = platform_settings.RUNTIME_RECONNECT_INTERVAL_SECONDS
        from app.core.lifecycle.redis import redis_manager

        try:
            while self.mode == "memory":
                try:
                    logger.info(EventID.LOG_INFO, "Recovery monitor probe attempt.")
                    self.breaker_state = "HALF_OPEN"
                    async with self._probe_lock:
                        # Disconnect first to ensure a fresh pool is initialized
                        with contextlib.suppress(Exception):
                            await redis_manager.disconnect()

                        # Attempt to refresh pool connections
                        with contextlib.suppress(Exception):
                            await redis_manager.connect()

                        if await self.redis_provider.ping():
                            logger.info(EventID.LOG_INFO, "Recovery Successful.")
                            self.mode = "redis"
                            self.active_provider = self.redis_provider
                            self.breaker_state = "CLOSED"
                            self.last_recovery_time = (
                                datetime.datetime.utcnow().isoformat() + "Z"
                            )
                            self.reconnect_count += 1
                            self.last_reconnection_time = self.last_recovery_time
                            DomainEventDispatcher.dispatch("RedisConnected", {})
                            DomainEventDispatcher.dispatch(
                                "RuntimeRecovered",
                                {
                                    "reconnect_count": self.reconnect_count,
                                    "time": self.last_reconnection_time,
                                },
                            )
                            DomainEventDispatcher.dispatch(
                                "RuntimeProviderChanged", {"new_provider": "redis"}
                            )
                            logger.info(
                                EventID.LOG_INFO,
                                "Redis Recovered",
                                details={
                                    "reconnect_count": self.reconnect_count,
                                    "time": self.last_reconnection_time,
                                },
                            )
                            break
                        raise Exception("Reconnection ping returned False")
                except BaseException as e:
                    self.breaker_state = "OPEN"
                    if isinstance(e, asyncio.CancelledError):
                        raise
                    self.failure_count += 1
                    self.last_failure_time = (
                        datetime.datetime.utcnow().isoformat() + "Z"
                    )
                    logger.debug(
                        EventID.LOG_INFO,
                        "Redis recovery poll failed, retrying.",
                        error=str(e),
                    )
                await asyncio.sleep(interval)
        finally:
            self.is_monitoring = False
            if self.breaker_state == "HALF_OPEN":
                self.breaker_state = "OPEN"
            logger.info(EventID.LOG_INFO, "Recovery monitor stopped.")

    def _queue_sync_event(self, event: tuple[str, str, Any]) -> None:
        """Safely queues a cache synchronization or invalidation event with coalescing."""
        if self._sync_queue is None:
            return

        action, key, extra = event

        # Enrich set event with absolute expiry if it has a TTL
        if action == "set" and extra is not None:
            val = extra[0]
            expire = extra[1] if len(extra) > 1 else None
            absolute_expiry = None
            if expire is not None:
                import time

                absolute_expiry = time.time() + expire
            extra = (val, expire, absolute_expiry)
            event = (action, key, extra)

        # Check queue warning threshold
        q_len = len(self._pending_keys)
        q_cap = self._sync_queue.maxsize
        if q_cap > 0:
            utilization = (q_len / q_cap) * 100.0
            crossed_threshold = 0
            if utilization >= 100.0:
                crossed_threshold = 100
            elif utilization >= 90.0:
                crossed_threshold = 90
            elif utilization >= 75.0:
                crossed_threshold = 75
            elif utilization >= 50.0:
                crossed_threshold = 50

            if crossed_threshold > self._last_crossed_threshold:
                logger.warning(
                    EventID.LOG_WARNING,
                    f"Cache sync queue utilization crossed {crossed_threshold}% threshold.",
                    details={
                        "size": q_len,
                        "capacity": q_cap,
                        "utilization": utilization,
                    },
                )
                self._last_crossed_threshold = crossed_threshold
            elif utilization < self._last_crossed_threshold:
                if utilization < 50.0:
                    self._last_crossed_threshold = 0
                elif utilization < 75.0:
                    self._last_crossed_threshold = 50
                elif utilization < 90.0:
                    self._last_crossed_threshold = 75
                else:
                    self._last_crossed_threshold = 90

        import time

        self._queue_timestamps[key] = time.time()

        if key in self._pending_keys:
            self._pending_keys[key] = event
            self.coalesced_events += 1
            return

        if self._sync_queue.full():
            self.dropped_events += 1
            logger.warning(
                EventID.LOG_WARNING,
                f"Cache sync queue is full (capacity {self._sync_queue.maxsize}). Dropping event.",
                details={
                    "capacity": self._sync_queue.maxsize,
                    "dropped_events": self.dropped_events,
                    "key": key,
                },
            )
        else:
            self._pending_keys[key] = event
            self._sync_queue.put_nowait(key)
            self.unique_events += 1

    def _should_replay_event(
        self, key: str, event: tuple[str, str, Any] | None = None
    ) -> bool:
        """Determines if a cached event should be replayed to Redis after an outage."""
        # 1. Expired cache check
        if event is not None and event[0] == "set" and event[2] is not None:
            extra = event[2]
            # extra format: (value, expire, absolute_expiry)
            if len(extra) > 2 and extra[2] is not None:
                import time

                if time.time() > extra[2]:
                    return False

        # 2. Maximum queue event age check
        import time

        queued_at = self._queue_timestamps.get(key)
        if (
            queued_at is not None
            and (time.time() - queued_at)
            > platform_settings.RUNTIME_QUEUE_MAX_EVENT_AGE_SECONDS
        ):
            return False

        # Normalize key for checking
        key_lower = key.lower()

        # Whitelist checks
        is_schema = "schema" in key_lower or "metadata" in key_lower
        is_template = "template" in key_lower
        is_lookup = "lookup" in key_lower
        is_test = "test" in key_lower

        # Blacklist checks
        is_progress = (
            "progress" in key_lower or "generation" in key_lower or "task" in key_lower
        )
        is_session = "session" in key_lower
        is_queue = "queue" in key_lower and not is_test

        # If it matches any blacklisted category, do NOT replay
        if is_progress or is_session or is_queue:
            return False

        # Only replay if it is in the whitelisted categories
        if is_schema or is_template or is_lookup or is_test:
            return True

        # Default fallback: do not replay unknown key types to avoid pollution
        return False

    async def _process_sync_queue(self) -> None:
        """Worker loop that processes cache invalidation/update requests from the queue with coalescing."""
        logger.info(EventID.LOG_INFO, "Worker Started")
        try:
            while True:
                if self._sync_queue is None:
                    await asyncio.sleep(1)
                    continue

                key = await self._sync_queue.get()
                event = self._pending_keys.pop(key, None)
                self._queue_timestamps.pop(key, None)
                if event is None:
                    self.skipped_events += 1
                    self._sync_queue.task_done()
                    continue

                if not self._should_replay_event(key, event):
                    self.skipped_events += 1
                    self._sync_queue.task_done()
                    continue

                action, _, extra = event
                success = False
                while not success:
                    # If in memory mode, wait until Redis is recovered
                    if self.mode == "memory":
                        await asyncio.sleep(
                            platform_settings.RUNTIME_SYNC_RETRY_INTERVAL_SECONDS
                        )
                        continue

                    try:
                        import time

                        start_time = time.time()
                        if action == "invalidate":
                            await self.redis_provider.delete(key)
                        elif action == "push_to_queue":
                            await self.redis_provider.push_to_queue(key, extra[0])
                        elif action == "delete":
                            await self.redis_provider.delete(key)
                        elif action == "sadd":
                            await self.redis_provider.sadd(key, *extra)
                        elif action == "srem":
                            await self.redis_provider.srem(key, *extra)
                        elif action == "set":
                            val_str = extra[0]
                            expire = extra[1] if len(extra) > 1 else None
                            await self.redis_provider.set(key, val_str, expire=expire)

                        duration = time.time() - start_time
                        self._total_sync_time += duration
                        self._total_sync_count += 1

                        success = True
                        self._sync_queue.task_done()
                    except Exception as e:
                        # Switch mode to memory and disconnect pool
                        logger.warning(
                            EventID.LOG_WARNING,
                            f"Background cache sync failed for action {action} on key {key}. Switching to Memory.",
                            error=str(e),
                        )
                        self.failure_count += 1
                        if (
                            self.failure_count
                            >= platform_settings.RUNTIME_CIRCUIT_BREAKER_FAILURE_THRESHOLD
                        ):
                            self.mode = "memory"
                            self.active_provider = self.memory_provider
                            self.breaker_state = "OPEN"
                            self.last_failure_time = (
                                datetime.datetime.utcnow().isoformat() + "Z"
                            )
                            from app.core.lifecycle.redis import redis_manager

                            with contextlib.suppress(Exception):
                                await redis_manager.disconnect()
                            DomainEventDispatcher.dispatch("RedisDisconnected", {})
                            DomainEventDispatcher.dispatch(
                                "RuntimeFallbackActivated", {"reason": str(e)}
                            )
                            DomainEventDispatcher.dispatch(
                                "RuntimeProviderChanged", {"new_provider": "memory"}
                            )
                            self.start_recovery_monitor()
                        await asyncio.sleep(
                            platform_settings.RUNTIME_SYNC_RETRY_INTERVAL_SECONDS
                        )
        finally:
            logger.info(
                EventID.LOG_INFO,
                "Worker Stopped",
                details={
                    "average_sync_time": self.average_sync_time,
                    "pending_queue_size": len(self._pending_keys),
                },
            )

    async def _execute_read(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        if self.mode == "redis" and self.breaker_state == "CLOSED":
            try:
                method = getattr(self.redis_provider, method_name)
                return await method(*args, **kwargs)
            except Exception as e:
                logger.error(
                    EventID.LOG_ERROR,
                    f"Runtime redis read method {method_name} failed. Falling back to Memory.",
                    error=str(e),
                )
                self.failure_count += 1
                if (
                    self.failure_count
                    >= platform_settings.RUNTIME_CIRCUIT_BREAKER_FAILURE_THRESHOLD
                ):
                    self.mode = "memory"
                    self.active_provider = self.memory_provider
                    self.breaker_state = "OPEN"
                    self.last_failure_time = (
                        datetime.datetime.utcnow().isoformat() + "Z"
                    )
                    from app.core.lifecycle.redis import redis_manager

                    with contextlib.suppress(Exception):
                        await redis_manager.disconnect()
                    DomainEventDispatcher.dispatch("RedisDisconnected", {})
                    DomainEventDispatcher.dispatch(
                        "RuntimeFallbackActivated", {"reason": str(e)}
                    )
                    DomainEventDispatcher.dispatch(
                        "RuntimeProviderChanged", {"new_provider": "memory"}
                    )
                    self.start_recovery_monitor()

        method = getattr(self.memory_provider, method_name)
        return await method(*args, **kwargs)

    async def _execute_write(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        # Write to memory provider synchronously
        method = getattr(self.memory_provider, method_name)
        await method(*args, **kwargs)

        # Queue the invalidate/write action in the background queue
        if self._sync_queue is not None:
            # We prefer invalidation for cache writes
            if method_name in ("set", "delete", "sadd", "srem"):
                key = args[0]
                self._queue_sync_event(("invalidate", key, None))
            elif method_name == "push_to_queue":
                queue_name = args[0]
                payload = args[1]
                self._queue_sync_event(("push_to_queue", queue_name, (payload,)))

    async def get(self, key: str) -> str | None:  # noqa: PLR0911
        val = await self._execute_read("get", key)
        if val is not None:
            return val  # type: ignore[no-any-return]

        # Fallback to SQLite (Source of Truth)
        import json

        from app.platform.container import get_persistence_provider

        if key.startswith("jobs:"):
            job_id = key.split(":", 1)[1]
            if job_id != "all_ids":
                try:
                    pers = get_persistence_provider()
                    job_dict = await pers.get_job(job_id)
                    if job_dict:
                        runtime_job = {
                            "jobId": job_dict["id"],
                            "type": job_dict["type"],
                            "status": job_dict["status"],
                            "startedAt": job_dict["started_at"],
                            "finishedAt": job_dict["finished_at"],
                            "duration": job_dict["duration"] or 0.0,
                            "progress": job_dict["progress"] or 0.0,
                            "resultSummary": job_dict["result_summary"],
                            "errorMessage": job_dict["error_message"],
                            "details": (
                                json.loads(job_dict["details_json"])
                                if job_dict.get("details_json")
                                else {}
                            ),
                        }
                        val_str = json.dumps(runtime_job)
                        await self.memory_provider.set(key, val_str)
                        if self.mode == "redis" and self._sync_queue is not None:
                            self._queue_sync_event(
                                (
                                    "set",
                                    key,
                                    (
                                        val_str,
                                        platform_settings.RUNTIME_CACHE_DEFAULT_TTL_SECONDS,
                                    ),
                                )
                            )
                        return val_str
                except Exception:  # noqa: S110
                    pass

        elif key.startswith("generation:") and key.endswith(":status"):
            workflow_id = key.split(":")[1]
            try:
                pers = get_persistence_provider()
                job_dict = await pers.get_job(workflow_id)
                if job_dict:
                    details = (
                        json.loads(job_dict["details_json"])
                        if job_dict.get("details_json")
                        else {}
                    )
                    progress = details.get("progress") or []
                    rows_gen = sum(p.get("rowsGenerated", 0) for p in progress)
                    status_dict = {
                        "workflowId": job_dict["id"],
                        "status": job_dict["status"],
                        "progress": progress,
                        "totalRowsGenerated": rows_gen,
                        "durationMs": (job_dict["duration"] or 0.0) * 1000.0,
                        "errors": (
                            [job_dict["error_message"]]
                            if job_dict["error_message"]
                            else []
                        ),
                    }
                    val_str = json.dumps(status_dict)
                    await self.memory_provider.set(key, val_str)
                    if self.mode == "redis" and self._sync_queue is not None:
                        self._queue_sync_event(
                            (
                                "set",
                                key,
                                (
                                    val_str,
                                    platform_settings.RUNTIME_CACHE_DEFAULT_TTL_SECONDS,
                                ),
                            )
                        )
                    return val_str
            except Exception:  # noqa: S110
                pass

        elif key.startswith("schema:"):
            project_id = key.split(":", 1)[1]
            try:
                pers = get_persistence_provider()
                schema_dict = await pers.get_active_schema(project_id)
                if schema_dict:
                    val_str = json.dumps(schema_dict)
                    await self.memory_provider.set(key, val_str)
                    if self.mode == "redis" and self._sync_queue is not None:
                        self._queue_sync_event(
                            (
                                "set",
                                key,
                                (
                                    val_str,
                                    platform_settings.RUNTIME_CACHE_DEFAULT_TTL_SECONDS,
                                ),
                            )
                        )
                    return val_str
            except Exception:  # noqa: S110
                pass

        elif key.startswith("metadata:"):
            job_id = key.split(":", 1)[1]
            try:
                pers = get_persistence_provider()
                meta_dict = await pers.get_metadata(job_id)
                if meta_dict:
                    val_str = json.dumps(meta_dict)
                    await self.memory_provider.set(key, val_str)
                    if self.mode == "redis" and self._sync_queue is not None:
                        self._queue_sync_event(
                            (
                                "set",
                                key,
                                (
                                    val_str,
                                    platform_settings.RUNTIME_CACHE_DEFAULT_TTL_SECONDS,
                                ),
                            )
                        )
                    return val_str
            except Exception:  # noqa: S110
                pass

        elif key.startswith("lookup:"):
            lookup_key = key.split(":", 1)[1]
            try:
                pers = get_persistence_provider()
                setting_str = await pers.get_app_setting(lookup_key)
                if setting_str is not None:
                    await self.memory_provider.set(key, setting_str)
                    if self.mode == "redis" and self._sync_queue is not None:
                        self._queue_sync_event(
                            (
                                "set",
                                key,
                                (
                                    setting_str,
                                    platform_settings.RUNTIME_CACHE_DEFAULT_TTL_SECONDS,
                                ),
                            )
                        )
                    return setting_str
            except Exception:  # noqa: S110
                pass

        elif key.startswith("template:"):
            template_key = key.split(":", 1)[1]
            try:
                pers = get_persistence_provider()
                template_str = await pers.get_app_setting(f"template:{template_key}")
                if template_str is not None:
                    await self.memory_provider.set(key, template_str)
                    if self.mode == "redis" and self._sync_queue is not None:
                        self._queue_sync_event(
                            (
                                "set",
                                key,
                                (
                                    template_str,
                                    platform_settings.RUNTIME_CACHE_DEFAULT_TTL_SECONDS,
                                ),
                            )
                        )
                    return template_str
            except Exception:  # noqa: S110
                pass

        return None

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        await self._execute_write("set", key, value, expire)

    async def delete(self, *keys: str) -> None:
        await self._execute_write("delete", *keys)

    async def sadd(self, key: str, *members: str) -> None:
        await self._execute_write("sadd", key, *members)

    async def srem(self, key: str, *members: str) -> None:
        await self._execute_write("srem", key, *members)

    async def smembers(self, key: str) -> builtins.set[str]:
        val = await self._execute_read("smembers", key)
        if val:
            return val  # type: ignore[no-any-return]

        # Fallback to SQLite
        if key == "jobs:all_ids":
            try:
                from app.platform.container import get_persistence_provider

                pers = get_persistence_provider()
                jobs = await pers.list_jobs("default")
                ids = {j["id"] for j in jobs}
                for j_id in ids:
                    await self.memory_provider.sadd(key, j_id)
                    if self.mode == "redis" and self._sync_queue is not None:
                        self._queue_sync_event(("sadd", key, (j_id,)))
                return ids
            except Exception:  # noqa: S110
                pass

        return set()

    async def keys(self, pattern: str) -> list[str]:
        val = await self._execute_read("keys", pattern)
        if val:
            return val  # type: ignore[no-any-return]

        # Fallback to SQLite
        if "jobs:" in pattern or pattern == "*":
            try:
                from app.platform.container import get_persistence_provider

                pers = get_persistence_provider()
                jobs = await pers.list_jobs("default")
                return [f"jobs:{j['id']}" for j in jobs]
            except Exception:  # noqa: S110
                pass

        return []

    async def push_to_queue(self, queue_name: str, payload: str) -> None:
        await self._execute_write("push_to_queue", queue_name, payload)

    async def pop_from_queue(
        self, queue_name: str, timeout_seconds: int = 0
    ) -> str | None:
        return await self._execute_read("pop_from_queue", queue_name, timeout_seconds)  # type: ignore[no-any-return]

    async def ping(self) -> bool:
        if self.mode == "redis":
            try:
                return await self.redis_provider.ping()
            except Exception:
                return False
        return True


# Process-wide singleton instance
runtime_manager = RuntimeManager()
