"""Serve the disposable native test workspace for optional live browser checks."""

import os
import sys
from pathlib import Path

os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://127.0.0.1:5173"
sys.path.insert(0, str(Path("backend/scripts").resolve()))
os.environ["SAI_RUNTIME"] = "1"
import system_smoke
import uvicorn

uvicorn.run(system_smoke.app, host="127.0.0.1", port=8000)
