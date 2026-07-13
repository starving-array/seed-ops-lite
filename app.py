"""Render entry point.

Serves the FastAPI application with React frontend at / and
API routes under /api/, /health, /schema/, etc.
All on a single port.
"""

import os
from pathlib import Path

os.environ["API_BASE_URL"] = ""

import uvicorn
from fastapi.staticfiles import StaticFiles

from app.main import create_api_app

# FastAPI with API routes
app = create_api_app()

# Serve React frontend at /
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
