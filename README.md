# Travel Planner — Multi-Agent Orchestration with Web UI

A proof-of-concept multi-agent system using **Microsoft Agent Framework (MAF)**
with **Ollama** for local LLM inference, served through a **FastAPI** backend
and **React/Next.js** frontend.

Three specialized agents collaborate in a sequential pipeline to produce
personalized travel itineraries, streamed in real-time via **Server-Sent Events (SSE)**.

```
User (Browser) → [Next.js Frontend] → [FastAPI API]
                                          ↓
                         [Researcher] → [WeatherAnalyst] → [Planner]
                                              ↓
                                       [MCP Tool Server]
```

## Features

- **Decoupled web architecture** — React frontend + FastAPI backend + PostgreSQL
- **In-process orchestration** via MAF `SequentialBuilder`
- **Ollama** for local LLM inference (GPU or CPU, no API keys required)
- **Real-time streaming** — SSE pipeline showing agent progress live in the browser
- **Multi-turn conversations** — persistent conversation history with context windowing
- **FastMCP** tool server in Docker container (Streamable HTTP)
- **OpenTelemetry** observability with Aspire Dashboard (traces + metrics + logs)
- **Architecture compliance tests** with pytest (190 tests)
- **Docker Compose** — full stack with GPU/CPU profiles
- **Configurable** via `.env` (model, endpoints, database, CORS)

## Prerequisites

- Docker Desktop (all services run in containers)
- NVIDIA GPU + CUDA (optional — CPU profile available)
- [Ollama](https://ollama.com/) model support

## Quick Start

### 1. Clone and Configure

```bash
cp .env.example .env
# Edit .env if you want to change the model, ports, or database settings
```

### 2. Start the Full Stack (GPU)

```bash
docker compose --profile gpu up -d
```

Or for CPU-only:

```bash
docker compose --profile cpu up -d
```

This starts:
- **Ollama** on port 11434 (LLM inference)
- **Ollama Init** — one-shot container that pulls the model
- **PostgreSQL** on port 5432 (conversation storage)
- **FastAPI** on port 8000 (REST + SSE API)
- **MCP Server** on port 8090 (travel tools: weather, time, restaurants)
- **Aspire Dashboard** on port 18888 (traces + metrics + logs)
- **Next.js Frontend** on port 3000 (web UI)

### 3. Open the App

Visit [http://localhost:3000](http://localhost:3000) to use the Travel Planner.

### 4. View Traces

Open [http://localhost:18888](http://localhost:18888) to view OpenTelemetry traces,
metrics, and structured logs.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama API endpoint |
| `OLLAMA_MODEL_ID` | `phi4-mini` | Ollama model name |
| `DATABASE_URL` | `postgresql+asyncpg://travel:travel@postgres:5432/travelplanner` | PostgreSQL connection |
| `MCP_SERVER_URL` | `http://mcp-server:8090/mcp` | MCP server endpoint |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://aspire-dashboard:18889` | OTLP gRPC endpoint |
| `OTEL_SERVICE_NAME` | `travel-planner-api` | Service name in traces |
| `API_HOST` | `0.0.0.0` | API server bind address |
| `API_PORT` | `8000` | API server port |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api` | Frontend → API URL |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/conversations` | Create a conversation |
| `GET` | `/api/conversations` | List conversations |
| `GET` | `/api/conversations/{id}` | Get conversation with messages |
| `DELETE` | `/api/conversations/{id}` | Delete a conversation |
| `POST` | `/api/conversations/{id}/messages` | Send message (SSE stream) |

### SSE Event Protocol

When sending a message, the API streams events:

```
event: workflow_started
data: {"workflow_id": "..."}

event: agent_started
data: {"agent_name": "Researcher", "step": 1}

event: agent_completed
data: {"agent_name": "Researcher", "step": 1, "content": "..."}

event: workflow_completed
data: {"workflow_id": "..."}
```

## Testing

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests (190 tests)
pytest tests/ -v

# By category
pytest tests/test_architecture.py -v     # Project structure compliance
pytest tests/test_config.py -v           # Configuration defaults
pytest tests/test_mcp_tools.py -v        # MCP tool unit tests
pytest tests/test_telemetry.py -v        # OTel setup
pytest tests/test_api_structure.py -v    # API structure validation
pytest tests/test_frontend_structure.py -v  # Frontend structure validation
pytest tests/test_workflow_patterns.py -v   # Workflow pattern compliance
pytest tests/test_telemetry_patterns.py -v  # Telemetry configuration
```

## Project Structure

```
├── docker-compose.yml               # Full stack (7 services)
├── .env.example                     # Environment template
├── requirements.txt                 # Host Python dependencies
├── scripts/
│   └── init-ollama.sh               # Model pull script
├── api/
│   ├── main.py                      # FastAPI app with lifespan
│   ├── Dockerfile                   # API container image
│   ├── requirements.txt             # API dependencies
│   ├── models/
│   │   ├── database.py              # SQLAlchemy async engine
│   │   ├── orm.py                   # Conversation + Message models
│   │   └── schemas.py              # Pydantic request/response schemas
│   ├── routes/
│   │   ├── health.py                # Health check endpoint
│   │   ├── conversations.py         # CRUD endpoints
│   │   └── messages.py              # SSE streaming endpoint
│   └── services/
│       ├── workflow.py              # MAF workflow → SSE bridge
│       └── session.py              # Multi-turn context builder
├── frontend/
│   ├── Dockerfile                   # Multi-stage Next.js build
│   ├── package.json                 # Dependencies
│   ├── next.config.ts               # Standalone output
│   └── src/
│       ├── app/                     # Next.js App Router pages
│       ├── components/              # React components
│       ├── hooks/                   # Custom hooks (SSE)
│       └── lib/                     # API client + types
├── src/
│   ├── config.py                    # Settings from env vars
│   ├── telemetry.py                 # OpenTelemetry setup
│   ├── agents/
│   │   ├── researcher.py            # Destination research
│   │   ├── weather_analyst.py       # Weather + MCP tools
│   │   └── planner.py              # Itinerary synthesis
│   └── workflows/
│       └── travel_planner.py        # Sequential pipeline
├── mcp_server/
│   ├── server.py                    # FastMCP tool server
│   └── Dockerfile                   # Container image
├── tests/                           # 190 compliance + unit tests
├── docs/                            # Architecture documentation
└── prototypes/                      # Early experiments
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Telemetry Guide](docs/telemetry-guide.md)
- [Adding New Agents](docs/adding-agents.md)
- [Creating Workflows](docs/creating-workflows.md)
- [Agent Design Guide](docs/agent-design-guide.md)

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | Microsoft Agent Framework (SequentialBuilder) |
| LLM Runtime | Ollama (local inference, GPU or CPU) |
| Backend API | FastAPI + Uvicorn (SSE streaming) |
| Frontend | React / Next.js 14 (TypeScript, Tailwind CSS) |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 async |
| Tool Protocol | Model Context Protocol (MCP) via FastMCP 3.0 |
| Observability | OpenTelemetry + Aspire Dashboard |
| Containers | Docker Compose (7 services, GPU/CPU profiles) |
| Language | Python 3.13 (backend), TypeScript (frontend) |
