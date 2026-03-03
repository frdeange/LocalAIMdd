"""
Travel Planner API Server
=========================
FastAPI application with lifespan management for:
- OllamaChatClient initialization
- Database connection setup
- MCP tool lifecycle
- OpenTelemetry instrumentation

Entry point:
    uvicorn api.main:app --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env BEFORE any MAF/OTel imports read environment variables
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.telemetry import setup_telemetry, shutdown_telemetry
from api.models.database import init_db, close_db
from api.routes.health import router as health_router
from api.routes.conversations import router as conversations_router
from api.routes.messages import router as messages_router

# ──────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("travel_planner.api")


# ──────────────────────────────────────────────────────────────
# Lifespan (startup + shutdown)
# ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — startup and shutdown.

    Startup:
        1. Initialize telemetry
        2. Create OllamaChatClient
        3. Initialize database tables
        4. Store shared state on app

    Shutdown:
        1. Close database connections
        2. Flush telemetry
    """
    settings = get_settings()

    # ── Startup ──────────────────────────────────────────────
    logger.info("Starting Travel Planner API...")

    # 1. Telemetry
    setup_telemetry(service_name=settings.otel_service_name)
    logger.info("Telemetry configured (OTLP → %s)", settings.otel_endpoint)

    # 2. Ollama client
    from agent_framework_ollama import OllamaChatClient

    client = OllamaChatClient(
        model_id=settings.ollama_model_id,
        host=settings.ollama_host,
    )
    logger.info("Ollama client ready — host: %s, model: %s",
                settings.ollama_host, settings.ollama_model_id)

    # 3. Database
    await init_db()
    logger.info("Database initialized (%s)", settings.database_url.split("@")[-1])

    # 4. Store shared state
    app.state.client = client
    app.state.mcp_server_url = settings.mcp_server_url
    app.state.settings = settings

    logger.info("=" * 60)
    logger.info("  Travel Planner API ready!")
    logger.info("  Ollama:  %s (%s)", settings.ollama_host, settings.ollama_model_id)
    logger.info("  MCP:     %s", settings.mcp_server_url)
    logger.info("  DB:      %s", settings.database_url.split("@")[-1])
    logger.info("  CORS:    %s", settings.cors_origins)
    logger.info("=" * 60)

    yield  # ← App is running

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("Shutting down Travel Planner API...")
    await close_db()
    shutdown_telemetry()
    logger.info("Shutdown complete")


# ──────────────────────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Travel Planner API",
    description="Multi-agent travel planning with MAF + Ollama",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(conversations_router, prefix="/api", tags=["conversations"])
app.include_router(messages_router, prefix="/api", tags=["messages"])
