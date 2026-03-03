"""Configuration for the ClaimsIQ backend."""

import os

LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4o")
HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "http://localhost:8888")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))

# Runtime override for Hindsight URL
_runtime_hindsight_url: str | None = None


def get_hindsight_url() -> str:
    return _runtime_hindsight_url or HINDSIGHT_API_URL


def set_hindsight_url(url: str):
    global _runtime_hindsight_url
    _runtime_hindsight_url = url
