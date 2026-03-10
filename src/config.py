"""
BMS Operations — Centralized Configuration
============================================
All environment-driven settings in one place.

Environment variables:
    OLLAMA_HOST       Ollama server URL     (default: http://localhost:11434)
    OLLAMA_MODEL_ID   Model to use          (default: qwen2.5:7b)
    OLLAMA_THINK      Enable reasoning      (default: false)
    BMS_LOG_LEVEL     Logging verbosity     (default: INFO)
    MCP_CAMERA_URL    MCP Camera server     (default: http://localhost:8090/mcp)
    MCP_WEATHER_URL   MCP Weather server    (default: http://localhost:8091/mcp)
    MCP_BMS_URL       MCP BMS server        (default: http://localhost:8093/mcp)
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ── Ollama / LLM ─────────────────────────────────────────────
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL_ID: str = os.getenv("OLLAMA_MODEL_ID", "qwen2.5:7b")
OLLAMA_THINK: bool = os.getenv("OLLAMA_THINK", "true").lower() in ("true", "1", "yes")

# ── MCP Services ─────────────────────────────────────────────
MCP_CAMERA_URL: str = os.getenv("MCP_CAMERA_URL", "http://localhost:8090/mcp")
MCP_WEATHER_URL: str = os.getenv("MCP_WEATHER_URL", "http://localhost:8091/mcp")
MCP_BMS_URL: str = os.getenv("MCP_BMS_URL", "http://localhost:8093/mcp")

# ── BMS Application ──────────────────────────────────────────
LOG_LEVEL: str = os.getenv("BMS_LOG_LEVEL", "INFO")

# ── Workflow Limits ───────────────────────────────────────────
# Maximum conversation length before forced termination
MAX_CONVERSATION_TURNS: int = int(os.getenv("BMS_MAX_TURNS", "30"))
