"""Application configuration."""

import os
from dotenv import load_dotenv

load_dotenv()

# Server Settings
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))
HINDSIGHT_PORT = int(os.environ.get("HINDSIGHT_PORT", "8888"))

# LLM Settings
LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4o")  # Default to gpt-4o
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Available models for the agent (frontend can select from these)
AVAILABLE_MODELS = [
    {"id": "openai/gpt-4o", "name": "GPT-4o", "description": "Balanced performance (default)"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "description": "Fast & cheap, good for simple tasks"},
    {"id": "openai/o1", "name": "o1", "description": "Reasoning model, slower but smarter"},
    {"id": "openai/o3-mini", "name": "o3 Mini", "description": "Latest reasoning model"},
]

# Hindsight Settings - can be overridden via API or per-request
HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", f"http://localhost:{HINDSIGHT_PORT}")

# Runtime-configurable hindsight URL (can be changed via /api/config endpoint)
_runtime_hindsight_url: str | None = None

def get_hindsight_url() -> str:
    """Get the current hindsight URL (runtime override or default)."""
    return _runtime_hindsight_url or HINDSIGHT_API_URL

def set_hindsight_url(url: str | None) -> None:
    """Set a runtime override for hindsight URL. Pass None to reset to default."""
    global _runtime_hindsight_url
    _runtime_hindsight_url = url

# Debug
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true")
