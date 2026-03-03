"""
BMS Operations — Centralized Configuration
============================================
All environment-driven settings in one place.

Environment variables:
    OLLAMA_HOST       Ollama server URL     (default: http://localhost:11434)
    OLLAMA_MODEL_ID   Model to use          (default: qwen2.5:3b)
    BMS_LOG_LEVEL     Logging verbosity     (default: INFO)
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ── Ollama / LLM ─────────────────────────────────────────────
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL_ID: str = os.getenv("OLLAMA_MODEL_ID", "qwen2.5:3b")

# ── BMS Application ──────────────────────────────────────────
LOG_LEVEL: str = os.getenv("BMS_LOG_LEVEL", "INFO")

# ── Workflow Limits ───────────────────────────────────────────
# Maximum conversation length before forced termination
MAX_CONVERSATION_TURNS: int = int(os.getenv("BMS_MAX_TURNS", "30"))
