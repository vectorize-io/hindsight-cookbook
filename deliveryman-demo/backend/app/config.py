"""Application configuration."""

import os
from dotenv import load_dotenv

load_dotenv()

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

# Hindsight Settings
HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "http://localhost:8888")

# Debug
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true")
