"""Upload the project to HF Space using huggingface_hub API."""
import os
from huggingface_hub import HfApi, login

token = os.environ.get("HF_TOKEN")
if not token:
    token = input("Paste your HF token: ").strip()

login(token=token, add_to_git_credential=False)
api = HfApi()

api.upload_folder(
    folder_path=".",
    repo_id="archeese/safeseedops-lite",
    repo_type="space",
    ignore_patterns=[
        ".venv/*",
        "__pycache__/*",
        "storage/*",
        "*.sqlite*",
        "models/*",
        ".git/*",
        ".gitignore",
        "upload_hf.py",
        ".env",
        ".env.*",
        "!requirements.txt",
    ],
)
print("Upload complete! Check https://huggingface.co/spaces/archeese/safeseedops-lite")
