"""Application configuration."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Settings
LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Hindsight Settings
HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "http://localhost:8888")

# Debug
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true")
