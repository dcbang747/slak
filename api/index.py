"""Vercel Python serverless entrypoint.

Vercel's Python runtime serves the module-level ASGI ``app``. We mount the real
FastAPI backend (in ``backend/app``) under ``/api`` so that the SPA's
``/api/<route>`` calls resolve to the backend's ``/<route>`` handlers — matching
how the Vite dev proxy strips the ``/api`` prefix locally.

This file is only used on Vercel; local dev/Docker runs ``backend/app/main.py``
directly via uvicorn, so the two never conflict.
"""

import pathlib
import sys

# Make the backend package importable (repo_root/backend on sys.path).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

from fastapi import FastAPI  # noqa: E402
from app.main import app as backend_app  # noqa: E402

app = FastAPI()
app.mount("/api", backend_app)
