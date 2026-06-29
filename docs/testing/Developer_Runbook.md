# Developer Runbook — SafeSeedOps Lite

Welcome to the **SafeSeedOps Lite** Developer Runbook! This document provides a step-by-step setup guide, startup procedures, and troubleshooting instructions for a new developer setting up the project from scratch.

---

## 1. Prerequisites

Before running the application, make sure the following tools are installed on your machine:

*   **Python**: Version `3.12` or `3.13` (recommended: python-3.13)
*   **Node.js**: Version `18` or higher (with `npm` package manager)
*   **Redis**: Version `7.0` or higher
*   **Docker & Docker Compose**: Optional but recommended for running Redis and multi-container deployments.
*   **uv**: The fast Python package manager and resolver. You can install it via:
    ```powershell
    # Windows PowerShell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
    ```bash
    # macOS/Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

---

## 2. Installing Dependencies

SafeSeedOps Lite has a decoupled architecture, with the backend built in Python (FastAPI) and the frontend built in React TypeScript (Vite).

### Backend Dependencies
From the repository root, install Python dependencies and set up the virtual environment:
```bash
uv sync
```
This automatically reads the `pyproject.toml` or `uv.lock` file, creates a `.venv` directory, and syncs all packages.

### Frontend Dependencies
Navigate to the `frontend/` directory and install npm packages:
```bash
cd frontend
npm install
```

---

## 3. Python Environment

Always use the resolved virtual environment managed by `uv`.
To execute commands within the context of the virtual environment, prefix them with `uv run`. For example:
*   To run Python: `uv run python`
*   To run pytest: `uv run pytest`
*   To run uvicorn: `uv run uvicorn`

---

## 4. Redis Setup

The backend relies on Redis as a key-value store to save schema configurations, track background generation jobs, and cache export files.

### Option A: Local Redis (Windows / WSL / macOS)
Start your local Redis server:
```bash
redis-server
```
Verify that Redis is listening on port `6379`.

### Option B: Redis via Docker (Recommended)
You can run Redis in a container using docker-compose:
```bash
docker compose up -d redis
```

---

## 5. Docker Setup

The repository provides a `docker-compose.yml` file to spin up both Redis and backend/frontend containers if desired.

To start all services:
```bash
docker compose up --build
```
To shut them down:
```bash
docker compose down
```

---

## 6. Environment Variables

The backend loads configuration settings from `.env`. The project contains a `.env.example` file you can copy:
```bash
copy .env.example .env
```

### Essential Settings in `.env`:
*   `APP_NAME`: Name of the application (default: `SafeSeedOps Lite`)
*   `APP_ENV`: Deployment profile (`development`, `production`, `testing`)
*   `REDIS_HOST`: Redis server hostname (default: `localhost`)
*   `REDIS_PORT`: Redis server port (default: `6379`)
*   `LOG_LEVEL`: Logging verbosity (`debug`, `info`, `warning`, `error`, `critical`)
*   `GEMINI_API_KEY`: Required for the AI Schema Assistant feature. Paste your Google AI Studio Gemini API key.

---

## 7. Running Backend

Start the FastAPI backend with uvicorn reloader enabled for development:
```bash
uv run uvicorn app.main:app --reload
```
The backend API documentation will be available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (Swagger UI) or [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc).

---

## 8. Running Frontend

Navigate to the `frontend/` directory and start the Vite dev server:
```bash
cd frontend
npm run dev
```
The frontend application will be served at [http://localhost:5173/](http://localhost:5173/).

---

## 9. Running Tests

To run the complete Python unit and integration test suite:
```bash
uv run pytest
```
To run tests with code coverage metrics:
```bash
uv run pytest --cov=app tests/
```

---

## 10. Running Quality Checks

Ensure code formatting and imports adhere to the repository quality gates:
```bash
# Lint check using Ruff
uv run ruff check app/ tests/

# Formatting check using Black
uv run black --check app/ tests/

# Static type checking using MyPy
uv run mypy app/
```

---

## 11. Running Repository Guardian

The Repository Guardian enforces repository health checks and verification stamps before allowing commits.

*   **Check status**: Run the full validation suite (Ruff, Black, MyPy, Pytest) and verify security configurations:
    ```bash
    uv run seed status
    ```
    If successful, this writes a verification stamp to `.seed/verification.json`.

*   **Commit changes**: Commit staged files (which blocks if the stamp is missing, unhealthy, or the repository has changed since status verification):
    ```bash
    uv run seed commit -m "feat(scope): descriptive message"
    ```

---

## 12. Common Startup Issues

### Issue 1: `TypeError: Formatter.__init__() got an unexpected keyword argument 'foreign_pre_processors'`
*   **Root Cause**: Outdated parameter reference in `structlog` logging initialization.
*   **Fix**: Update `app/core/logging/logging.py` to use `foreign_pre_chain` instead of `foreign_pre_processors`.

### Issue 2: `redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379`
*   **Root Cause**: Redis server is offline or running on a non-default port.
*   **Fix**: Start Redis using `redis-server` or `docker compose up -d redis`.

### Issue 3: `FastAPI client hangs during AI Schema Assistant execution`
*   **Root Cause**: Missing or invalid `GEMINI_API_KEY` in environment variables.
*   **Fix**: Check your `.env` file, populate `GEMINI_API_KEY="AIzaSy..."`, and restart the FastAPI server.

---

## 13. Troubleshooting Guide

*   **Verify Redis connectivity**: Run `redis-cli ping`. It should reply with `PONG`.
*   **Clean build caches**: If the frontend exhibits caching anomalies:
    ```bash
    cd frontend
    rm -rf dist node_modules
    npm install
    ```
*   **Inspect logs**: System trace logs are recorded in the `logs/` directory. Check `logs/app.log` for application error traces.
