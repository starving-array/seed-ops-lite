"""HF Spaces Gradio SDK entry point.

Starts the FastAPI API server in a background thread,
then launches the Gradio UI as the main process.
"""

import os
import threading

os.environ["API_BASE_URL"] = "http://127.0.0.1:8000"

import uvicorn
from app.main import create_api_app
from app.ui.gradio_app import create_gradio_app

fastapi_app = create_api_app()
server = threading.Thread(
    target=uvicorn.run,
    args=(fastapi_app,),
    kwargs={"host": "127.0.0.1", "port": 8000, "log_level": "info"},
    daemon=True,
)
server.start()

app = create_gradio_app()
app.launch(server_name="0.0.0.0", ssr_mode=False)
