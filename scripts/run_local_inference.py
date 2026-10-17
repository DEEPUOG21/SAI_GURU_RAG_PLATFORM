"""Optional local inference launcher for a real CPU smoke test. No secret is printed."""

import os
import runpy
import secrets
from pathlib import Path

key_file = Path(".local-inference-key")
if not key_file.exists():
    key_file.write_text(secrets.token_urlsafe(48))
os.environ["INFERENCE_API_KEY"] = key_file.read_text()
os.environ["HF_HOME"] = str(Path(".model-cache").resolve())
os.environ["FASTEMBED_CACHE_PATH"] = str(Path(".model-cache").resolve())
os.environ.setdefault("MODEL_THREADS", "4")
runpy.run_path("inference/server.py", run_name="__main__")
