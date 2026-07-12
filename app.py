"""HF Spaces / Render entry point.

Serves the React frontend at /, Gradio UI at /gradio,
and API routes under /api/, /health, /schema/, etc.
All on a single port.
"""

import os
from pathlib import Path

os.environ["API_BASE_URL"] = ""

import uvicorn
from fastapi.staticfiles import StaticFiles
from gradio import mount_gradio_app
from gradio.themes import Soft as SoftTheme

from app.main import create_api_app
from app.ui.gradio_app import GRADIO_CSS, create_gradio_app

# FastAPI with API routes
app = create_api_app()

# Mount Gradio UI at /gradio
gradio_app = create_gradio_app()
app = mount_gradio_app(
    app,
    gradio_app,
    path="/gradio",
    theme=SoftTheme(primary_hue="red"),
    css=GRADIO_CSS,
    show_error=True,
)

# Serve React frontend at /
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
