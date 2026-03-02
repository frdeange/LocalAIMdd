# AGENTS.md — GitHub Copilot Agent Instructions

> This file provides context for GitHub Copilot to work effectively with this codebase.
> Read this file FIRST before making any changes.

## Project Overview

**Travel Planner** — A multi-agent orchestration PoC using **Microsoft Agent Framework (MAF)** with **Ollama** for local LLM inference, served through a decoupled web architecture: **FastAPI** backend + **React/Next.js** frontend + **PostgreSQL** persistence.

- **Language**: Python 3.13 (backend), TypeScript (frontend)
- **Package Manager**: pip (backend), npm (frontend)

## Architecture

```
User (Browser) → [Next.js :3000] → [FastAPI :8000] → [MAF SequentialBuilder]
                                                          ↓
                                    [Researcher] → [WeatherAnalyst] → [Planner]
                                                         ↓
                                                  [MCP Server :8090]
```

### Runtime Components

| Component | Technology | Location | Port |
|-----------|-----------|----------|------|
| Frontend | Next.js 14 + React + Tailwind | Docker container | 3000 |
| API Server | FastAPI + Uvicorn | Docker container | 8000 |
| LLM Runtime | Ollama | Docker container | 11434 |
| Orchestrator | MAF SequentialBuilder | In API process | — |
| MCP Server | FastMCP 3.0 (Streamable HTTP) | Docker container | 8090 |
| Database | PostgreSQL 16 | Docker container | 5432 |
| Observability | Aspire Dashboard | Docker container | 18888 (UI), 4317→18889 (OTLP gRPC) |

### Key Data Flow

1. User sends message via frontend → FastAPI POST `/api/conversations/{id}/messages`
2. API loads conversation context from PostgreSQL, builds context prefix
3. `run_workflow_sse()` builds MAF workflow, streams SSE events back
4. `SequentialBuilder` chains 3 agents with shared `list[Message]` context
5. WeatherAnalyst connects to MCP server via `MCPStreamableHTTPTool`
6. Agent responses streamed as SSE events: `agent_started` → `agent_completed`
7. Completed messages persisted to PostgreSQL
8. Frontend renders pipeline progress + markdown responses in real-time

## Project Structure

```
├── docker-compose.yml               # 7 services, GPU/CPU profiles
├── .env.example                     # Environment template
├── requirements.txt                 # Host Python dependencies
├── scripts/
│   └── init-ollama.sh               # Model pull on first run
│
├── api/
│   ├── main.py                      # FastAPI app with lifespan
│   ├── Dockerfile                   # OTel auto-instrumented
│   ├── requirements.txt             # API-specific dependencies
│   ├── models/
│   │   ├── database.py              # SQLAlchemy async engine + session
│   │   ├── orm.py                   # Conversation + Message ORM
│   │   └── schemas.py              # Pydantic schemas + SSE events
│   ├── routes/
│   │   ├── health.py                # GET /api/health
│   │   ├── conversations.py         # CRUD endpoints
│   │   └── messages.py              # SSE streaming endpoint
│   └── services/
│       ├── workflow.py              # MAF workflow → SSE bridge
│       └── session.py              # Multi-turn context builder
│
├── frontend/
│   ├── Dockerfile                   # Multi-stage standalone build
│   ├── package.json                 # React, Next.js, Tailwind
│   └── src/
│       ├── app/                     # Next.js App Router pages
│       ├── components/              # Chat, ConversationList, PipelineStatus, MessageBubble
│       ├── hooks/                   # useSSE custom hook
│       └── lib/                     # API client (api.ts) + TypeScript types
│
├── src/
│   ├── config.py                    # Settings from env vars (dataclass)
│   ├── telemetry.py                 # OTel setup, custom spans/metrics
│   ├── agents/
│   │   ├── __init__.py              # Re-exports all agent factories
│   │   ├── researcher.py            # LLM-only: destination research
│   │   ├── weather_analyst.py       # MCP tools: weather, time, restaurants
│   │   └── planner.py              # LLM-only: itinerary synthesis
│   └── workflows/
│       ├── __init__.py              # Re-exports workflow builder
│       └── travel_planner.py        # SequentialBuilder pipeline
│
├── mcp_server/
│   ├── server.py                    # FastMCP tool definitions + /health
│   ├── Dockerfile                   # OTel auto-instrumented
│   └── requirements.txt             # fastmcp, opentelemetry
│
├── tests/                           # 190 compliance + unit tests
│   ├── test_architecture.py         # Project structure compliance
│   ├── test_config.py               # Settings defaults and env loading
│   ├── test_mcp_tools.py            # MCP tool unit tests (parametrized)
│   ├── test_telemetry.py            # OTel setup and span helpers
│   ├── test_telemetry_patterns.py   # OTel config validation
│   ├── test_workflow_patterns.py    # Workflow structure and patterns
│   ├── test_api_structure.py        # API module/route/service validation
│   └── test_frontend_structure.py   # Frontend component/config validation
│
├── docs/
│   ├── architecture.md              # System architecture diagram
│   ├── telemetry-guide.md           # OTel + Aspire setup guide
│   ├── adding-agents.md             # How to add new agents
│   ├── agent-design-guide.md        # Prompt engineering for SLMs
│   └── creating-workflows.md        # SequentialBuilder usage
│
└── prototypes/                      # Early experiments (not production)
    ├── main.py                      # MCPStdioTool prototype
    ├── main_openai.py               # Direct OpenAI client prototype
    ├── main_foundry.py              # Original FoundryLocal main
    └── mstest.py                    # Basic FoundryLocal test
```

## Code Conventions

### Agent Pattern

Every agent follows the factory function pattern:

```python
# src/agents/{name}.py
from agent_framework import Agent

def create_{name}_agent(client: object) -> Agent:
    return client.as_agent(
        name="AgentName",
        instructions="...",
        tools=[...],  # Only if agent uses tools
    )
```

- Agents with tools return `tuple[Agent, MCPStreamableHTTPTool]`
- Agents without tools return `Agent` directly
- All agents registered in `src/agents/__init__.py`

### API Pattern

```python
# api/routes/{name}.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.database import get_db

router = APIRouter()

@router.get("/endpoint")
async def handler(db: AsyncSession = Depends(get_db)):
    ...
```

- Routes use dependency injection for DB sessions
- SSE streaming uses `StreamingResponse(media_type="text/event-stream")`
- Schemas defined in `api/models/schemas.py`

### Frontend Pattern

```typescript
// frontend/src/components/ComponentName.tsx
"use client";
import { useState, useEffect } from "react";

interface Props { ... }

export default function ComponentName({ ... }: Props) { ... }
```

- All components are client components (`"use client"`)
- Custom hooks in `src/hooks/`
- API client in `src/lib/api.ts`
- Types in `src/lib/types.ts`

### MCP Tool Pattern

```python
# mcp_server/server.py
from fastmcp import FastMCP

mcp = FastMCP(name="TravelTools")

@mcp.tool()
def tool_name(param: Annotated[str, "description"]) -> str:
    """Tool docstring becomes MCP description."""
    ...
```

### Configuration

All config via environment variables, loaded from `.env`:

| Variable | Default | Used By |
|----------|---------|---------|
| `OLLAMA_HOST` | `http://ollama:11434` | API server |
| `OLLAMA_MODEL_ID` | `phi4-mini` | API server |
| `DATABASE_URL` | `postgresql+asyncpg://travel:travel@postgres:5432/travelplanner` | API server |
| `MCP_SERVER_URL` | `http://mcp-server:8090/mcp` | API server |
| `CORS_ORIGINS` | `http://localhost:3000` | API server |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://aspire-dashboard:18889` | API + MCP containers |
| `OTEL_SERVICE_NAME` | `travel-planner-api` | API server |
| `API_HOST` | `0.0.0.0` | API server |
| `API_PORT` | `8000` | API server |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api` | Frontend |

### Telemetry

- API server: Auto-instrumented via `opentelemetry-instrument` CLI wrapper in Dockerfile
- MCP server: Auto-instrumented via `opentelemetry-instrument` CLI wrapper in Dockerfile
- Custom spans: `trace_workflow()`, `trace_agent()` context managers in `src/telemetry.py`
- Custom metrics: `workflow.duration`, `agent.duration`, `mcp.tool_calls`

### Testing

```bash
pytest tests/ -v          # All tests (~190)
pytest tests/ -v -k api   # API-related only
pytest tests/ -v -k frontend  # Frontend-related only
```

- Tests are **structural/compliance** — they validate code patterns, not runtime behavior
- Tests read source files to check for patterns (imports, config, structure)
- No mocking of LLM calls — agents are tested via architecture compliance
- MCP tool functions are unit-tested directly (imported from `mcp_server.server`)

## Docker Infrastructure

### Start/Stop

```bash
# GPU mode
docker compose --profile gpu up -d

# CPU mode
docker compose --profile cpu up -d

# Stop
docker compose --profile gpu down  # or --profile cpu

# Rebuild after changes
docker compose build --no-cache api      # API changes
docker compose build --no-cache frontend  # Frontend changes
docker compose build --no-cache mcp-server  # MCP changes
```

### Container Details

**Ollama** (`travel-ollama`):
- Image: `ollama/ollama:latest`
- Profiles: `gpu` (NVIDIA runtime) or `cpu` (no GPU)
- Volume: `ollama-models` for model persistence

**Ollama Init** (one-shot):
- Runs `scripts/init-ollama.sh` to pull model
- Exits after model is ready

**PostgreSQL** (`travel-postgres`):
- Image: `postgres:16-alpine`
- Volume: `postgres-data` for data persistence
- Healthcheck: `pg_isready`

**API** (`travel-api`):
- Custom from `api/Dockerfile` (build context: `.`)
- CMD: `opentelemetry-instrument uvicorn api.main:app`
- Healthcheck: `GET /api/health` every 10s
- Depends on: postgres, mcp-server, aspire-dashboard

**MCP Server** (`travel-mcp-server`):
- Custom from `mcp_server/Dockerfile`
- CMD: `opentelemetry-instrument python server.py`
- Healthcheck: `GET /health` every 10s

**Frontend** (`travel-frontend`):
- Custom from `frontend/Dockerfile` (3-stage build)
- Standalone Next.js output
- Depends on: api

**Aspire Dashboard** (`travel-aspire-dashboard`):
- Image: `mcr.microsoft.com/dotnet/aspire-dashboard:latest`
- Auth: disabled

## Common Tasks

### Add a New MCP Tool

1. Add function in `mcp_server/server.py` with `@mcp.tool()` decorator
2. Add unit tests in `tests/test_mcp_tools.py`
3. Rebuild: `docker compose build --no-cache mcp-server`

### Add a New Agent

1. Create `src/agents/{name}.py` following factory pattern
2. Export from `src/agents/__init__.py`
3. Wire into workflow in `src/workflows/travel_planner.py`
4. Update `AGENT_SEQUENCE` in `api/services/workflow.py`
5. Update `AGENT_PIPELINE` in `frontend/src/lib/types.ts`
6. Add tests, rebuild API: `docker compose build --no-cache api`

### Add a New API Route

1. Create `api/routes/{name}.py` with `APIRouter()`
2. Import and include in `api/main.py`
3. Add Pydantic schemas in `api/models/schemas.py`
4. Add tests in `tests/test_api_structure.py`

### Run End-to-End

```bash
# Prerequisites: Docker running, GPU available (or use cpu profile)
docker compose --profile gpu up -d
# Wait for ollama-init to finish pulling the model
# Open http://localhost:3000
# View traces at http://localhost:18888
```

## External Documentation

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Ollama](https://ollama.com/)
- [FastMCP 3.0 Docs](https://gofastmcp.com/)
- [Aspire Dashboard](https://learn.microsoft.com/en-us/dotnet/aspire/fundamentals/dashboard/standalone)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [Next.js 14 Docs](https://nextjs.org/docs)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
