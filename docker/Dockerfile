# ==============================================================================
# Stage 1 — Build dependencies (uv sync)
# ==============================================================================
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_VERSION=0.4.30 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /build

COPY pyproject.toml uv.lock* ./

# Install only production dependencies
RUN /root/.cargo/bin/uv sync --frozen --no-dev --no-install-project

# ==============================================================================
# Stage 2 — Runtime (CPU)
# ==============================================================================
FROM python:3.12-slim AS runner

LABEL org.opencontainers.image.source=https://github.com/starving-array/seed-ops-lite

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Create non-privileged user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -d /app -s /sbin/nologin -c "Application User" appuser

# Copy virtual environment from builder
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Copy application code
COPY app/ /app/app/
COPY .env* /app/

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:${PORT}/health'); exit(0 if r.is_success else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
