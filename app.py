"""Render entry point.

Serves the FastAPI application with React frontend at / and
API routes under /api/, /health, /schema/, etc.
All on a single port.
"""

import os
from pathlib import Path

os.environ["API_BASE_URL"] = ""

import uvicorn
from fastapi.responses import FileResponse

from app.main import create_api_app

# FastAPI with API routes
app = create_api_app()

frontend_dist = Path(__file__).parent / "frontend" / "dist"

# Serve landing page at /
@app.get("/", response_class=FileResponse)
async def landing() -> FileResponse:
    return FileResponse(str(frontend_dist / "index-landing.html"))

# Serve React SPA at /app (catch-all for client-side routing)
@app.get("/app", response_class=FileResponse)
@app.get("/app/{rest:path}", response_class=FileResponse)
async def serve_frontend(rest: str = "") -> FileResponse:
    file_path = frontend_dist / rest
    if rest and file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    return FileResponse(str(frontend_dist / "index.html"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
