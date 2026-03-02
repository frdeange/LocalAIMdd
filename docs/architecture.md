# Architecture Overview

## Travel Planner — Multi-Agent Orchestration with Web UI

### System Context

This project implements a **multi-agent orchestration** proof-of-concept using the
[Microsoft Agent Framework (MAF)](https://github.com/microsoft/agent-framework) with
**Ollama** as the local LLM runtime, served through a decoupled web architecture:
**FastAPI** backend + **React/Next.js** frontend + **PostgreSQL** persistence.

### Architecture Diagrams

> **Generated diagrams** — These are auto-generated from Python scripts.
> Regenerate after architecture changes:
>
> ```bash
> # Using the 'diagrams' library (requires graphviz):
> pip install diagrams && apt-get install graphviz
> python docs/generate_architecture.py
>
> # Using PIL (no graphviz needed):
> pip install Pillow
> python docs/generate_architecture_png.py
> ```

#### Platform Architecture (diagrams library)

![Travel Planner Architecture](images/travel_planner_architecture.png)

#### Platform Architecture (PIL version)

![Travel Planner Architecture — PIL](images/travel_planner_architecture_pil.png)

#### ASCII Reference (Docker Compose — original)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Docker Compose Stack                           │
│                                                                         │
│  ┌──────────────┐      ┌───────────────────────────────────────────┐    │
│  │  Next.js      │ HTTP │  FastAPI (api)                            │    │
│  │  Frontend     │─────→│  :8000                                    │    │
│  │  :3000        │  SSE │                                           │    │
│  └──────────────┘      │  ┌─────────┐  Sequential  ┌────────────┐  │    │
│                        │  │Researcher│────────────→│ Weather    │  │    │
│                        │  │(LLM only)│            │ Analyst    │  │    │
│                        │  └─────────┘            │ (MCP tools)│  │    │
│                        │                         └─────┬──────┘  │    │
│                        │                               │         │    │
│                        │                         ┌─────▼──────┐  │    │
│                        │                         │ Planner    │  │    │
│                        │                         │ (LLM only) │  │    │
│                        │                         └────────────┘  │    │
│                        │                                          │    │
│                        │  OllamaChatClient ←→ Ollama (:11434)    │    │
│                        │  SQLAlchemy async ←→ PostgreSQL (:5432)  │    │
│                        │  OpenTelemetry SDK ──→ OTLP Exporter    │    │
│                        └───────────────────────────────────────────┘    │
│                                │ HTTP              │ gRPC               │
│                                ▼                   ▼                    │
│  ┌──────────────────────────┐  ┌───────────────────────────────────┐    │
│  │   MCP Server (Docker)    │  │   Aspire Dashboard (Docker)      │    │
│  │   FastMCP (port 8090)    │  │   UI (port 18888)                │    │
│  │   + OTel auto-instrument │──│→ OTLP gRPC (port 18889)          │    │
│  │   Streamable HTTP        │  │   OTLP gRPC (ext. port 4317)    │    │
│  └──────────────────────────┘  └───────────────────────────────────┘    │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │  Ollama       │  │  PostgreSQL  │  │  Ollama Init (one-shot)     │  │
│  │  :11434       │  │  :5432       │  │  Pulls model on first run   │  │
│  │  GPU or CPU   │  │  + volumes   │  │  depends_on: ollama         │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Decoupled frontend + API + DB | Independent scaling, modern web UX, persistent conversations |
| Orchestration | In-process (SequentialBuilder) | MAF's native pattern; agents share the same process and conversation context |
| LLM Runtime | Ollama (Docker) | Local inference, GPU + CPU support, no API keys, model via `ollama pull` |
| Backend | FastAPI + SSE | Async-native, streaming support, auto-docs, Pydantic validation |
| Frontend | React / Next.js 14 | TypeScript, App Router, standalone Docker output, Tailwind CSS |
| Database | PostgreSQL + SQLAlchemy async | Reliable persistence, async support, conversation history |
| Agent-to-Agent | Shared conversation (list[Message]) | SequentialBuilder passes messages down the chain automatically |
| External Tools | FastMCP (Streamable HTTP) | Single MCP server in Docker, no auth, port 8090 |
| Observability | OpenTelemetry → Aspire Dashboard | Distributed tracing across API, MCP server, and dashboard |
| Configuration | `.env` + env vars | 12-factor compatible, Docker Compose env_file |
| Profiles | GPU/CPU Docker Compose profiles | Same compose file supports both GPU and CPU-only setups |

### Components

#### 1. Frontend (Next.js)

- **Technology**: React 18, Next.js 14, TypeScript, Tailwind CSS
- **Transport**: HTTP REST + SSE (ReadableStream API)
- **Features**:
  - Conversation sidebar with create/delete
  - Real-time agent pipeline visualization (3-step indicator)
  - Markdown rendering for agent responses
  - Agent name badges with per-agent colors
  - Mobile-responsive layout
- **Docker**: Multi-stage build (deps → build → standalone runner)

#### 2. API Server (FastAPI)

- **Technology**: FastAPI, Uvicorn, SQLAlchemy 2.0 async, asyncpg
- **Endpoints**: REST CRUD + SSE streaming on `/api/conversations/{id}/messages`
- **Lifespan**: Initializes OllamaChatClient, database, and telemetry on startup
- **Features**:
  - Conversation CRUD with cascade delete
  - Multi-turn context windowing (~4096 token budget)
  - SSE event protocol: `workflow_started` → `agent_started` → `agent_completed` → `workflow_completed`
  - CORS configuration for frontend origin
  - Health check endpoint
- **Docker**: OTel auto-instrumented via `opentelemetry-instrument uvicorn`

#### 3. Agents (In-Process within API)

| Agent | Role | Tools |
|-------|------|-------|
| **Researcher** | Gathers destination info (culture, attractions, transport) | None (LLM knowledge) |
| **WeatherAnalyst** | Fetches and analyzes weather, time, dining options | `get_weather`, `get_current_time`, `search_restaurants` via MCP |
| **Planner** | Synthesizes research + weather into a travel itinerary | None (LLM synthesis) |

All agents are created via `OllamaChatClient.as_agent()` and wired into a
`SequentialBuilder(participants=[...]).build()` workflow.

#### 4. MCP Server (Docker Container)

- **Technology**: FastMCP 3.0, Python 3.13
- **Transport**: Streamable HTTP on port 8090 (`/mcp` endpoint)
- **Tools**: `get_weather`, `get_current_time`, `search_restaurants`
- **Telemetry**: Auto-instrumented via `opentelemetry-instrument`
- **Data**: Mock data (hardcoded dictionaries — PoC scope)

#### 5. Ollama (Docker Container)

- **Profiles**: `gpu` (with NVIDIA runtime) or `cpu` (without)
- **Shared container**: Both profiles use `container_name: travel-ollama`
- **Init**: One-shot container `ollama-init` runs `ollama pull ${model}` on first start
- **Volume**: `ollama-models` persists downloaded models across restarts

#### 6. PostgreSQL (Docker Container)

- **Image**: `postgres:16-alpine`
- **Tables**: `conversations` + `messages` (auto-created via SQLAlchemy `create_all`)
- **Volume**: `postgres-data` for persistence
- **Healthcheck**: `pg_isready` every 5s

#### 7. Observability (Aspire Dashboard)

- **Collects**: Traces, metrics, and structured logs via OTLP gRPC
- **Services reporting**: `travel-planner-api` (FastAPI) + `travel-mcp-tools` (MCP server)
- **Ports**: 18888 (UI), 18889 (OTLP gRPC internal), 4317 (OTLP gRPC external)

### Data Flow

```
User types message in browser
    │
    ▼
Frontend sends POST /api/conversations/{id}/messages
    │ (SSE stream response)
    ▼
┌──────────────────────────────────────────────────────┐
│  API builds context from conversation history        │
│  API calls run_workflow_sse(client, mcp_url, query)  │
│                                                      │
│  SequentialBuilder Workflow                           │
│                                                      │
│  1. Researcher receives user query + context          │
│     → SSE: agent_started, agent_completed            │
│     → Produces: Research Brief                        │
│                                                      │
│  2. WeatherAnalyst receives conversation so far      │
│     → Calls MCP tools: get_weather, get_current_time │
│     → SSE: agent_started, agent_completed            │
│     → Produces: Weather Analysis                     │
│                                                      │
│  3. Planner receives full conversation               │
│     → SSE: agent_started, agent_completed            │
│     → Produces: Complete Travel Itinerary            │
│                                                      │
│  SSE: workflow_completed                             │
│  Messages persisted to PostgreSQL                     │
└──────────────────────────────────────────────────────┘
    │
    ▼
Frontend renders pipeline progress + agent responses
```

### Project Structure

```
localOrchestration/
├── docker-compose.yml               # 7 services, GPU/CPU profiles
├── .env.example                     # Environment template
├── requirements.txt                 # Host Python dependencies
├── scripts/
│   └── init-ollama.sh               # Model pull on first run
├── api/
│   ├── main.py                      # FastAPI app + lifespan
│   ├── Dockerfile                   # OTel auto-instrumented
│   ├── requirements.txt             # API dependencies
│   ├── models/
│   │   ├── database.py              # Async engine + session factory
│   │   ├── orm.py                   # Conversation + Message ORM
│   │   └── schemas.py              # Pydantic schemas + SSE events
│   ├── routes/
│   │   ├── health.py                # GET /api/health
│   │   ├── conversations.py         # CRUD endpoints
│   │   └── messages.py              # SSE streaming endpoint
│   └── services/
│       ├── workflow.py              # MAF → SSE event bridge
│       └── session.py              # Context window builder
├── frontend/
│   ├── Dockerfile                   # Multi-stage standalone
│   ├── package.json                 # React, Next.js, Tailwind
│   ├── next.config.ts               # standalone output
│   └── src/
│       ├── app/                     # Pages + layout
│       ├── components/              # Chat, ConversationList, etc.
│       ├── hooks/                   # useSSE custom hook
│       └── lib/                     # API client + TypeScript types
├── src/
│   ├── config.py                    # Settings from env vars
│   ├── telemetry.py                 # OTel setup + custom spans
│   ├── agents/
│   │   ├── researcher.py            # Research agent factory
│   │   ├── weather_analyst.py       # Weather agent + MCP tool
│   │   └── planner.py              # Planner agent factory
│   └── workflows/
│       └── travel_planner.py        # SequentialBuilder workflow
├── mcp_server/
│   ├── server.py                    # FastMCP tool server
│   ├── Dockerfile                   # OTel auto-instrumented
│   └── requirements.txt             # Server dependencies
├── tests/
│   ├── test_architecture.py         # Project structure (190 tests total)
│   ├── test_config.py               # Config module tests
│   ├── test_mcp_tools.py            # MCP tool unit tests
│   ├── test_telemetry.py            # Telemetry tests
│   ├── test_telemetry_patterns.py   # OTel config validation
│   ├── test_workflow_patterns.py    # Workflow pattern tests
│   ├── test_api_structure.py        # API structure validation
│   └── test_frontend_structure.py   # Frontend structure validation
├── docs/
│   ├── architecture.md              # This document
│   ├── telemetry-guide.md           # OTel + Aspire setup guide
│   ├── adding-agents.md             # How to add new agents
│   ├── creating-workflows.md        # How to create workflows
│   └── agent-design-guide.md        # Agent prompt design
└── prototypes/                      # Early experiments
    ├── main.py                      # MCPStdioTool prototype
    ├── main_openai.py               # Direct OpenAI client prototype
    ├── main_foundry.py              # Original FoundryLocal main
    └── mstest.py                    # Basic test script
```
