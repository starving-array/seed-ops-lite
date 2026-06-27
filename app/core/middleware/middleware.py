"""Middleware modules for tracking correlation IDs and logging/exception handling."""

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.context.context import (
    ExecutionContext,
    reset_context,
    set_context,
)
from app.core.exceptions.exceptions import SeedOpsError
from app.core.logging.logging import correlation_id_ctx, logger

# Header name for tracking requests
CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts or generates a unique correlation ID.

    Applies to every request.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process incoming requests to inject the Correlation ID.

        Args:
            request: The incoming FastAPI request.
            call_next: The next middleware or endpoint handler in the chain.

        Returns:
            Response: The HTTP response with the correlation ID attached.
        """
        # Retrieve from header if present, else generate new UUID
        correlation_id = request.headers.get(CORRELATION_HEADER)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        request_id = str(uuid.uuid4())

        # Set legacy ContextVar for backward compatibility
        legacy_token = correlation_id_ctx.set(correlation_id)

        # Set the modern unified ExecutionContext
        new_context = ExecutionContext(
            request_id=request_id,
            correlation_id=correlation_id,
            request_start_time=time.perf_counter(),
        )
        context_token = set_context(new_context)

        try:
            response = await call_next(request)
            response.headers[CORRELATION_HEADER] = correlation_id
            return response
        finally:
            # Reset ContextVars to prevent leakage
            correlation_id_ctx.reset(legacy_token)
            reset_context(context_token)


class ExceptionLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that intercepts exceptions, logs them, and formats responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process the request, timing execution and trapping errors.

        Args:
            request: The incoming FastAPI request.
            call_next: The next middleware or endpoint handler in the chain.

        Returns:
            Response: The HTTP response or custom JSON error response.
        """
        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        from app.telemetry.events import EventID

        logger.info(
            EventID.HTTP_RECEIVED,
            "Incoming request",
            component="Middleware",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            logger.info(
                EventID.HTTP_COMPLETED,
                "Request completed",
                duration_ms=round(duration * 1000.0, 2),
                component="Middleware",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
            )
            return response

        except SeedOpsError as exc:
            duration = time.perf_counter() - start_time
            logger.warning(
                EventID.LOG_WARNING,
                "Domain exception caught in middleware",
                duration_ms=round(duration * 1000.0, 2),
                component="Middleware",
                method=request.method,
                path=request.url.path,
                status_code=exc.status_code,
                error=exc.message,
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "error": {
                        "type": exc.__class__.__name__,
                        "message": exc.message,
                        "correlation_id": correlation_id_ctx.get(),
                    },
                },
            )

        except Exception as exc:  # pylint: disable=broad-except
            duration = time.perf_counter() - start_time
            logger.exception(
                EventID.LOG_ERROR,
                "Unhandled exception caught in middleware",
                duration_ms=round(duration * 1000.0, 2),
                component="Middleware",
                method=request.method,
                path=request.url.path,
                error=str(exc),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": {
                        "type": "InternalServerError",
                        "message": "An unexpected error occurred on the server.",
                        "correlation_id": correlation_id_ctx.get(),
                    },
                },
            )
