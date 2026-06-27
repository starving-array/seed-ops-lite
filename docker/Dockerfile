# ==============================================================================
# Build Stage
# ==============================================================================
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Install dependencies needed for compiling packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${POETRY_HOME}/bin:${PATH}"

WORKDIR /build

# Copy configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies (only production packages)
RUN poetry install --only main --no-root

# ==============================================================================
# Production Stage
# ==============================================================================
FROM python:3.12-slim AS runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Create a non-privileged user to run the app
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -d /app -s /sbin/nologin -c "Application User" appuser

# Copy virtual environment from builder stage
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Copy application code
COPY app/ /app/app/
COPY .env* /app/

# Set ownership of the application directory to the non-root user
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE ${PORT}

# Run the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
