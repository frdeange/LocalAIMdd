"""
Configuration Module
====================
Centralized settings loaded from environment variables and .env file.
Uses python-dotenv for local development and standard os.environ for production.

All defaults use Docker service names for container-to-container communication.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load .env file (no-op if not present)
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings resolved from environment variables.

    Attributes:
        ollama_host: Ollama server URL (e.g. "http://ollama:11434").
        ollama_model_id: Ollama model identifier (e.g. "phi4-mini").
        mcp_server_url: URL of the FastMCP HTTP server.
        otel_endpoint: OTLP gRPC endpoint for telemetry export.
        otel_service_name: Service name tag for telemetry spans.
        api_host: Bind address for the FastAPI server.
        api_port: Port for the FastAPI server.
        cors_origins: Comma-separated list of allowed CORS origins.
        database_url: Async PostgreSQL connection string.
    """

    # ── Ollama ────────────────────────────────────────────────
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://ollama:11434")
    )
    ollama_model_id: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL_ID", "phi4-mini")
    )

    # ── MCP ───────────────────────────────────────────────────
    mcp_server_url: str = field(
        default_factory=lambda: os.getenv("MCP_SERVER_URL", "http://mcp-server:8090/mcp")
    )

    # ── Telemetry ─────────────────────────────────────────────
    otel_endpoint: str = field(
        default_factory=lambda: os.getenv(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://aspire-dashboard:18889"),
        )
    )
    otel_service_name: str = field(
        default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "travel-planner-api")
    )

    # ── API Server ────────────────────────────────────────────
    api_host: str = field(
        default_factory=lambda: os.getenv("API_HOST", "0.0.0.0")
    )
    api_port: int = field(
        default_factory=lambda: int(os.getenv("API_PORT", "8000"))
    )
    cors_origins: str = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000")
    )

    # ── Database ──────────────────────────────────────────────
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://travel:travel@postgres:5432/travelplanner",
        )
    )


def get_settings() -> Settings:
    """Create and return a Settings instance from current environment."""
    return Settings()
