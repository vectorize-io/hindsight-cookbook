"""Configuration for the CableConnect backend."""

import os

LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4o")
HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY", "")
HINDSIGHT_BANK_NAME = os.environ.get("HINDSIGHT_BANK_NAME", "cable-connect-demo")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8002"))

# Runtime override for Hindsight URL
_runtime_hindsight_url: str | None = None


def get_hindsight_url() -> str:
    return _runtime_hindsight_url or HINDSIGHT_API_URL


def set_hindsight_url(url: str):
    global _runtime_hindsight_url
    _runtime_hindsight_url = url
