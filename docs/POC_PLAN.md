# BMS PoC — Detailed Implementation Plan

> **Date:** 2026-03-03
> **Repository:** `frdeange/LocalAIMdd` (GitHub) / `kiko/LocalAIMdd` (Gitea)
> **Branch:** `main`

---

## Table of Contents

1. [Current State (What Is Already Validated)](#1-current-state)
2. [Target Architecture](#2-target-architecture)
3. [Phase Overview](#3-phase-overview)
4. [Phase 0 — Foundation (COMPLETED)](#phase-0--foundation-completed)
5. [Phase 1 — MCP Services](#phase-1--mcp-services)
6. [Phase 2 — BMS Database & API](#phase-2--bms-database--api)
7. [Phase 3 — Agent Integration (MCP + BMS Tools)](#phase-3--agent-integration)
8. [Phase 4 — BMS Frontend Dashboard](#phase-4--bms-frontend-dashboard)
9. [Phase 5 — Speech Layer (STT + TTS)](#phase-5--speech-layer)
10. [Phase 6 — Voice UI (Walkie-Talkie)](#phase-6--voice-ui)
11. [Phase 7 — End-to-End Integration](#phase-7--end-to-end-integration)
12. [Phase 8 — Kubernetes Deployment](#phase-8--kubernetes-deployment)
13. [Phase 9 — Validation & Demo](#phase-9--validation--demo)
14. [Risk Register](#risk-register)
15. [Infrastructure Reference](#infrastructure-reference)

---

## 1. Current State

### What Has Been Validated

| Item | Status | Evidence |
|---|---|---|
| MAF HandoffBuilder — agent routing via tool calling | ✅ Validated | L2 and L3 workflows run correctly |
| MAF ConcurrentBuilder — parallel fan-out/fan-in | ✅ Validated | Camera ∥ Meteo execute concurrently |
| Agent-as-facade — nesting workflows as agents | ✅ Validated | ReconAgent wraps L1, FieldSpecialist wraps L2 |
| 3-level nested architecture (L1+L2+L3) | ✅ Validated | Full demo completed on K8s |
| Ollama + qwen2.5:7b with tool calling | ✅ Validated | Routing works (not perfect, but functional) |
| MAF Ollama kwargs bug workaround | ✅ Validated | Monkey-patch in `src/patch_ollama.py` |
| Inner HITL auto-response mechanism | ✅ Validated | L2 facade auto-responds to inner HITL |
| Dockerfile + container image build | ✅ Validated | Image pushed to Nexus registry |
| K8s deployment (bms-ops namespace) | ✅ Validated | Pod ran demo successfully |
| GitOps pipeline (Gitea → ArgoCD) | ✅ Validated | Auto-sync works |
| Cross-namespace Ollama connectivity | ✅ Validated | bms-ops→maflocal DNS resolution works |

### What Exists in Code

```
src/
├── __init__.py, __main__.py       # Package + CLI entry point
├── config.py                      # Environment-driven config
├── client.py                      # OllamaChatClient factory
├── patch_ollama.py                # MAF bug #4402 workaround
├── runner.py                      # Interactive + demo runner
├── agents/
│   ├── camera.py                  # CameraAgent (leaf, no MCP yet)
│   ├── meteo.py                   # MeteoAgent (leaf, no MCP yet)
│   ├── vehicle.py                 # VehicleExpert (leaf)
│   ├── case_manager.py            # CaseManager (no DB yet)
│   ├── field_coordinator.py       # FieldCoordinator (L2 router)
│   └── orchestrator.py            # Orchestrator (L3 router)
└── workflows/
    ├── recon.py                   # L1: ConcurrentBuilder + facade
    ├── field.py                   # L2: HandoffBuilder + facade
    └── operations.py              # L3: HandoffBuilder (top-level)
```

### What Is NOT Yet Implemented

| Component | Current State |
|---|---|
| MCP Camera Service | Agent generates text from LLM — no MCP server |
| MCP Weather Service | Agent generates text from LLM — no MCP server |
| MCP BMS Service | CaseManager hallucinates case IDs — no MCP, no PostgreSQL |
| BMS REST API | No API exists — runner.py drives workflow directly |
| BMS Frontend | No dashboard — output is terminal text only |
| Speech-to-Text | No STT — input is typed text or demo script |
| Text-to-Speech | No TTS — output is printed text only |
| Voice UI | No web interface for voice interaction |
| K8s manifests for new components | Only bms-operations deployment exists |

---

## 2. Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OPERATOR                                   │
│              (walkie-talkie web UI)                           │
└─────────┬───────────────────────────────────┬───────────────┘
          │ audio (record)                     ▲ audio (playback)
          ▼                                    │
┌─────────────────────────────────────────────────────────────┐
│                 SPEECH SERVICE                                │
│          faster-whisper STT  ←→  Piper TTS                   │
│               (GPU, offline, Spanish es-ES)                   │
└─────────┬───────────────────────────────────┬───────────────┘
          │ text                               ▲ text
          ▼                                    │
┌─────────────────────────────────────────────────────────────┐
│                   BMS API (FastAPI)                           │
│  ┌───────────┐  ┌────────────────┐  ┌───────────────────┐   │
│  │ /messages  │  │  /cases (read) │  │  /stream SSE      │   │
│  │ (operator  │  │  (dashboard)   │  │  (live updates)   │   │
│  │  input)    │  │                │  │                   │   │
│  └─────┬─────┘  └───────┬────────┘  └───────────────────┘   │
│        │                │ (read-only from DB for UI)          │
│        ▼                │                                     │
│  ┌─────────────────────────────────┐                          │
│  │  MAF Workflow Engine            │                          │
│  │  (3-level nested architecture)  │                          │
│  └──┬──────────────┬───────────┬───┘                          │
│     │              │           │                               │
└─────┼──────────────┼───────────┼──────────────────────────────┘
      │ MCP          │ MCP       │ MCP
      ▼              ▼           ▼
┌────────────┐ ┌────────────┐ ┌─────────────────────────┐
│ MCP Camera │ │MCP Weather │ │ MCP BMS Service         │
│  Service   │ │  Service   │ │ (case CRUD → PostgreSQL)│
└────────────┘ └────────────┘ └─────────────────────────┘

   All backed by:  Ollama (GPU) → qwen2.5:7b
```

---

## 3. Phase Overview

| Phase | Name | Depends On | Deliverables |
|---|---|---|---|
| 0 | Foundation | — | ✅ COMPLETED — agent architecture validated |
| 1 | MCP Services | 0 | MCP Camera + Weather + BMS servers, agent tool integration |
| 2 | BMS Database & API | 1* | PostgreSQL schema, FastAPI (dashboard/SSE), (*depends on MCP BMS from Phase 1) |
| 3 | Agent Integration | 1, 2 | Agents use MCP tools exclusively (Camera, Weather, BMS) |
| 4 | BMS Frontend | 2 | Live dashboard showing cases and interactions |
| 5 | Speech Layer | 0 | faster-whisper STT + Piper TTS (GPU, Spanish es-ES) |
| 6 | Voice UI | 4, 5 | Walkie-talkie web interface |
| 7 | End-to-End Integration | 3, 6 | Voice → Agents → BMS → Dashboard flow |
| 8 | K8s Deployment | 7 | All components containerised and deployed |
| 9 | Validation & Demo | 8 | Full scenario test + demo recording |

```
Phase 0 ──── DONE
  │
  ├──→ Phase 1 (MCP Services) ───┐
  │                               ├──→ Phase 3 (Agent Integration) ──┐
  ├──→ Phase 2 (BMS DB + API) ───┘                                   │
  │         │                                                         │
  │         └──→ Phase 4 (Frontend) ──┐                               │
  │                                    │                               │
  ├──→ Phase 5 (Speech Layer) ────────┼──→ Phase 6 (Voice UI) ───────┤
                                       │                               │
                                       └───────────────────────────────┤
                                                                       │
                                                          Phase 7 (E2E Integration)
                                                                       │
                                                          Phase 8 (K8s Deployment)
                                                                       │
                                                          Phase 9 (Validation)
```

> **Phases 1, 2, and 5 can be developed in parallel** — they have no
> inter-dependencies.

---

## Phase 0 — Foundation (COMPLETED)

**Status: ✅ DONE**

All items completed in previous sessions:

- [x] MAF pattern research and prototype validation
- [x] 3-level nested workflow architecture implemented
- [x] 6 agents created with detailed instructions
- [x] Agent-as-facade pattern for workflow nesting
- [x] Monkey-patch for MAF Ollama kwargs bug (#4402)
- [x] Demo runner (interactive + scripted)
- [x] Dockerfile and container image in Nexus
- [x] K8s manifests (namespace, configmap, deployment)
- [x] ArgoCD GitOps pipeline
- [x] Gitea repo with full code push
- [x] GitHub repo synchronised
- [x] Cluster reorganised: `shared-services` namespace with Ollama, `maflocal` deleted
- [x] GPU time-slicing configured (3 replicas per physical GPU)

---

## Phase 1 — MCP Services

**Goal:** Create three MCP tool servers (Camera, Weather, BMS) that
agents call via the Model Context Protocol. This validates the
architectural principle: **all external system access from agents goes
through MCP — no exceptions.**

### Technology: FastMCP v3.1+

All MCP servers **MUST** be built with **FastMCP ≥ 3.1**
([gofastmcp.com](https://gofastmcp.com)).

| Aspect | Detail |
|---|---|
| Framework | FastMCP v3.1+ (`pip install fastmcp`) |
| Transport | **streamable-http** (for both K8s and local dev) |
| Telemetry | **Built-in** — FastMCP generates OTel traces; export via `OTEL_EXPORTER_OTLP_ENDPOINT` env var |
| Python | 3.13 |

### Validated: MAF → MCP Integration Pattern

MAF provides **native MCP client support** via `MCPStreamableHTTPTool`.
No manual tool wrappers or HTTP client code needed.

```python
# Validated agent factory pattern (src/agents/camera.py)
from agent_framework import Agent, MCPStreamableHTTPTool
from src.config import MCP_CAMERA_URL

def create_camera_agent(client):
    camera_mcp = MCPStreamableHTTPTool(
        name="camera_mcp",
        url=MCP_CAMERA_URL,   # env-driven: http://localhost:8090/mcp
        description="Surveillance camera system",
    )
    return client.as_agent(
        name="CameraAgent",
        instructions=CAMERA_INSTRUCTIONS,
        tools=[camera_mcp],
    )
```

> **Key discovery:** `MCPStreamableHTTPTool(name, url)` auto-discovers
> all tools exposed by the FastMCP server. The agent sees them as
> callable functions. The LLM decides which to call based on its
> instructions and the tool descriptions.

### Port Assignments

| MCP Server | Port | Endpoint | Env var (URL) |
|---|---|---|---|
| Camera | 8090 | `http://<host>:8090/mcp` | `MCP_CAMERA_URL` |
| Weather | 8091 | `http://<host>:8091/mcp` | `MCP_WEATHER_URL` |
| BMS | 8093 | `http://<host>:8093/mcp` | `MCP_BMS_URL` |

### 1.1 MCP Camera Service

**File:** `mcp_services/camera_server.py`

| Detail | Value |
|---|---|
| Framework | **FastMCP ≥ 3.1** |
| Transport | **streamable-http** on port 8090 |
| Tool: `get_camera_feed` | Input: `latitude: float`, `longitude: float`, `zoom_level: int` |
| Output | JSON: `{ target_description, image_quality, visibility, tactical_notes }` |
| Behaviour | Deterministic mock — returns pre-defined observations based on coordinate quadrant |

**Implementation details:**

```python
# Coordinate-based sectors for deterministic simulation
SECTORS = {
    "NE": {"target": "Dark green SUV parked near warehouse", ...},
    "NW": {"target": "Open field, no activity detected", ...},
    "SE": {"target": "Two military-type trucks, convoy formation", ...},
    "SW": {"target": "Civilian sedan, single occupant", ...},
}
```

- Coordinates mapped to quadrants (lat ≥ 0 → N, lon ≥ 0 → E)
- Returns consistent data for same coordinates (reproducible demos)
- Simulate 1-2 second delay (camera repositioning time)

### 1.2 MCP Weather Service

**File:** `mcp_services/weather_server.py`

| Detail | Value |
|---|---|
| Tool: `get_weather_report` | Input: `latitude: float`, `longitude: float` |
| Output | JSON: `{ temperature_c, conditions, wind_speed_kmh, wind_direction, visibility_km, humidity_pct, precipitation, risk_level, forecast_6h }` |
| Behaviour | Deterministic mock based on coordinate sector |

**Implementation details:**

- Same quadrant mapping as Camera
- Risk levels: LOW / MODERATE / HIGH / SEVERE
- Forecast provides 6-hour outlook
- Simulate 0.5 second delay

### 1.3 MCP BMS Service

**File:** `mcp_services/bms_server.py`

| Detail | Value |
|---|---|
| Framework | **FastMCP ≥ 3.1** |
| Transport | **streamable-http** on port 8093 |
| Database | PostgreSQL (async via `asyncpg`) |
| Tools | `create_case`, `update_case`, `add_interaction`, `get_case`, `list_cases` |

**Tool definitions:**

| Tool | Input | Output |
|---|---|---|
| `create_case` | `summary: str`, `priority: str`, `coordinates: str` | `{ case_id, status, created_at }` |
| `update_case` | `case_id: str`, `status: str?`, `priority: str?` | `{ case_id, updated_fields }` |
| `add_interaction` | `case_id: str`, `agent_name: str`, `message: str` | `{ interaction_id, timestamp }` |
| `get_case` | `case_id: str` | `{ case, interactions[] }` |
| `list_cases` | `status: str?` (optional filter) | `{ cases[] }` |

**Implementation details:**

- Case ID generation: sequential `BMS-{YEAR}-{NNN}`
- Real PostgreSQL CRUD (this is NOT simulated — it persists actual data)
- Emits notifications when cases/interactions are created (for SSE stream)
- Connection string from environment variable `DATABASE_URL`

```python
@mcp.tool()
async def create_case(summary: str, priority: str = "MEDIUM",
                      coordinates: str = "") -> str:
    """Create a new BMS incident case."""
    case_id = await generate_next_case_id()
    await db.execute(
        "INSERT INTO cases (case_id, summary, priority, coordinates) ...",
        case_id, summary, priority, coordinates
    )
    return json.dumps({"case_id": case_id, "status": "OPEN"})
```

### 1.4 MCP Service Requirements File

**File:** `mcp_services/requirements.txt`

```
fastmcp>=3.1.0
asyncpg          # PostgreSQL async driver (for MCP BMS)
```

### 1.5 Agent Updates — Wire MCP Tools

Modify Camera and Meteo agents to call MCP tools instead of
generating text from the LLM.

**Key decision:** MAF supports MCP tool integration. The agents need to
be configured with MCP tool references so the LLM calls them via
tool-calling, and the framework routes the call to the MCP server.

**Option A — MAF native MCP plugin:**
If MAF has built-in MCP client support, use it to connect agents to
MCP servers. This is the preferred approach.

**Option B — Manual tool functions:**
Create Python tool functions that internally call the MCP server
(via `mcp` client SDK) and register them as agent tools. This is
the fallback if MAF's MCP integration doesn't support Ollama well.

> **Research needed:** Verify MAF's MCP plugin compatibility with
> OllamaChatClient before implementation.

### 1.6 Testing

- Unit test: MCP Camera returns expected data for known coordinates
- Unit test: MCP Weather returns expected data for known coordinates
- Unit test: MCP BMS creates/reads/updates cases in PostgreSQL
- Integration test: CameraAgent calls MCP tool and includes result in response
- Integration test: MeteoAgent calls MCP tool and includes result in response
- Integration test: CaseManager creates a case via MCP BMS tool

### Acceptance Criteria

- [x] MCP Camera server runs standalone and responds to tool calls
- [x] MCP Weather server runs standalone and responds to tool calls
- [x] MCP BMS server runs standalone and performs real CRUD on PostgreSQL
- [x] CameraAgent uses MCP tool (not LLM hallucination) for observations
- [ ] MeteoAgent uses MCP tool (not LLM hallucination) for weather data
- [ ] CaseManager uses MCP BMS tools for case persistence (not hallucination)
- [ ] L1 ConcurrentBuilder still works with MCP-enabled agents
- [x] Demo produces deterministic, reproducible sensor data
- [x] Cases and interactions are persisted in PostgreSQL after demo run
- [x] MCP transport is streamable-http (not stdio)
- [ ] OTel traces export when OTEL_EXPORTER_OTLP_ENDPOINT is set

---

## Phase 2 — BMS Database & API

**Goal:** Create the BMS REST API (FastAPI) for operator-facing concerns:
message ingestion, SSE streaming for the dashboard, and frontend serving.
The database schema is created here, but **agents write to the DB via the
MCP BMS Service (Phase 1)** — the REST API is read-only for case data
(dashboard queries) plus the operator message entry point.

### 2.1 PostgreSQL Schema

**File:** `bms_api/db/schema.sql`

Uses the existing PostgreSQL in the `db` namespace. Create a new
database `bms_ops` (or schema within an existing DB).

```sql
CREATE TABLE cases (
    case_id       VARCHAR(12) PRIMARY KEY,  -- BMS-2026-001
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status        VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    priority      VARCHAR(10) NOT NULL DEFAULT 'MEDIUM',
    summary       TEXT NOT NULL,
    coordinates   JSONB,                    -- {lat, lon}
    metadata      JSONB DEFAULT '{}'
);

CREATE TABLE interactions (
    interaction_id  SERIAL PRIMARY KEY,
    case_id         VARCHAR(12) NOT NULL REFERENCES cases(case_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_name      VARCHAR(50) NOT NULL,
    message         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_interactions_case ON interactions(case_id);
CREATE INDEX idx_cases_status ON cases(status);
```

### 2.2 BMS REST API

**File:** `bms_api/main.py`

| Technology | Choice |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy (async) or raw asyncpg |
| Validation | Pydantic v2 |

**Endpoints:**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/messages` | Operator message → triggers MAF workflow → returns response |
| `GET` | `/api/cases` | List cases (read-only, for dashboard) |
| `GET` | `/api/cases/{id}` | Get case with interactions (read-only, for dashboard) |
| `GET` | `/api/stream` | SSE stream of new cases/interactions (for live dashboard) |
| `POST` | `/api/voice` | Voice message (audio) → STT → workflow → TTS → audio response |
| `GET` | `/api/health` | Health check |

> **Note:** Case creation and updates are NOT exposed as REST endpoints.
> Agents write to the BMS exclusively through the MCP BMS Service.
> The REST API reads from the same PostgreSQL for dashboard display.

**SSE Stream (`/api/stream`):**
- Emits events when new cases or interactions are created
- Frontend subscribes on load for live updates
- Format: `event: new_interaction\ndata: {JSON}\n\n`

### 2.3 Case ID Generation

Sequential within the year: `BMS-{YEAR}-{NNN}`

```python
# Query: SELECT MAX(case_id) FROM cases WHERE case_id LIKE 'BMS-2026-%'
# Increment the sequence number
```

### 2.4 BMS API Project Structure

```
bms_api/
├── __init__.py
├── main.py              # FastAPI app + endpoints
├── config.py            # DB connection + MCP service URLs
├── models.py            # SQLAlchemy models (read-only queries for dashboard)
├── schemas.py           # Pydantic schemas
├── db/
│   ├── __init__.py
│   ├── connection.py    # Async engine + session factory
│   └── schema.sql       # DDL (shared with MCP BMS service)
├── services/
│   ├── __init__.py
│   ├── queries.py       # Read-only DB queries for dashboard/SSE
│   └── workflow.py      # MAF workflow integration
├── static/              # Dashboard UI files (Phase 4)
├── Dockerfile
└── requirements.txt
```

### 2.5 Workflow Integration

The `/api/messages` endpoint is the bridge between the operator and MAF:

```python
@app.post("/api/messages")
async def handle_message(body: OperatorMessage):
    # 1. Run MAF workflow (agents handle case creation/updates
    #    via MCP BMS tools internally)
    response = await run_workflow(body.text)

    # 2. Return response text (for TTS later)
    return {"response": response}
```

> **Key difference from previous design:** The API does NOT create cases
> or log interactions directly. The Orchestrator routes to CaseManager,
> which calls MCP BMS tools (`create_case`, `add_interaction`). This
> keeps the architectural principle: agents own all BMS writes via MCP.

### 2.6 Testing

- Unit test: Case CRUD operations
- Unit test: Interaction creation and retrieval
- Unit test: SSE stream emits events
- Integration test: `/api/messages` processes operator text and returns response

### Acceptance Criteria

- [ ] PostgreSQL schema created in cluster DB
- [ ] FastAPI app runs and passes health check
- [ ] Dashboard can read cases and interactions from DB
- [ ] SSE stream emits live events when MCP BMS writes to DB
- [ ] `/api/messages` endpoint invokes MAF workflow and returns response

---

## Phase 3 — Agent Integration

**Goal:** Wire all agents to their MCP tools — Camera, Weather, and BMS.
All external system access from agents goes through MCP exclusively.

### 3.1 CaseManager Agent — MCP BMS Tools

The CaseManager agent connects to the MCP BMS Service. The LLM decides
WHEN to call which tool based on its instructions. Available tools:

| MCP Tool | When CaseManager calls it |
|---|---|
| `create_case` | First operator report → new incident |
| `update_case` | Priority change, status update, close case |
| `add_interaction` | Log agent findings, operator messages |
| `get_case` | Retrieve current case details |
| `list_cases` | List open/active cases |

**Integration pattern:** Same as Camera/Weather — via MAF MCP plugin or
manual tool wrapper calling the MCP BMS server.

### 3.2 Camera Agent — MCP Tool

Wire the CameraAgent to call the MCP Camera Service tool
(`get_camera_feed`). Two options:

**If using MAF MCP plugin:**
```python
agent = Agent(
    ...,
    plugins=[MCPPlugin(server_url="http://mcp-camera:8090")]
)
```

**If using manual tool wrapper:**
```python
@kernel_function(description="Get camera surveillance feed for coordinates")
async def get_camera_feed(latitude: float, longitude: float, zoom_level: int = 5) -> str:
    async with mcp_client("http://mcp-camera:8090") as client:
        result = await client.call_tool("get_camera_feed", {
            "latitude": latitude, "longitude": longitude, "zoom_level": zoom_level
        })
        return json.dumps(result)
```

### 3.3 Meteo Agent — MCP Tool

Same pattern as Camera but for the Weather MCP service.

### 3.4 Integration Adjustments

- Update `src/workflows/recon.py` — ReconAgent facade may need adjustments
  if agents now have tool functions (they'll async-call MCP during
  ConcurrentBuilder execution)
- Verify L1 ConcurrentBuilder handles agents with async tools correctly
- Verify L2 HandoffBuilder routes to agents with tools correctly
- Verify CaseManager MCP BMS calls work within L3 HandoffBuilder context

### Acceptance Criteria

- [ ] CaseManager creates real cases in PostgreSQL via MCP BMS tools
- [ ] CaseManager updates cases (status, priority) via MCP BMS tools
- [ ] CameraAgent calls MCP Camera for observations (no hallucination)
- [ ] MeteoAgent calls MCP Weather for conditions (no hallucination)
- [ ] Full 3-level workflow runs with all real MCP tools connected
- [ ] Demo scenario produces persistent data in PostgreSQL
- [ ] All agent-to-external-system communication goes through MCP (zero direct REST/DB calls)

---

## Phase 4 — BMS Frontend Dashboard

**Goal:** Real-time web dashboard showing cases and interactions.

### 4.1 Technology

| Choice | Reasoning |
|---|---|
| **Next.js** or **plain HTML + SSE** | Keep it simple — SSE from API |
| **Tailwind CSS** | Quick styling |
| Alternative: pure **FastAPI + Jinja2** templates | Zero build step, simplest option |

> **Recommendation:** Use FastAPI serving static HTML + vanilla JS +
> SSE for maximum simplicity. No build step, no Node.js dependency.
> This is a PoC, not a production webapp.

### 4.2 Dashboard Features

| Feature | Priority |
|---|---|
| List of cases with status badges | Must have |
| Case detail view with interaction timeline | Must have |
| Live updates via SSE (new interactions appear automatically) | Must have |
| Status indicators (OPEN/IN_PROGRESS/CLOSED) | Must have |
| Priority colour coding | Nice to have |
| Audio playback of operator messages | Phase 6 |

### 4.3 File Structure

```
bms_api/
└── static/
    ├── index.html          # Dashboard SPA
    ├── style.css           # Tailwind or minimal CSS
    └── app.js              # SSE subscription + DOM updates
```

Served by FastAPI: `app.mount("/", StaticFiles(directory="static"))`

### 4.4 SSE Integration

```javascript
const events = new EventSource("/api/stream");
events.addEventListener("new_case", (e) => { addCaseToList(JSON.parse(e.data)); });
events.addEventListener("new_interaction", (e) => { appendInteraction(JSON.parse(e.data)); });
events.addEventListener("case_update", (e) => { updateCaseStatus(JSON.parse(e.data)); });
```

### Acceptance Criteria

- [ ] Dashboard loads and shows existing cases
- [ ] New cases appear in real time when created by agents
- [ ] Interaction timeline updates live
- [ ] Accessible via ingress at `bms.maf.local` (or similar)

---

## Phase 5 — Speech Layer

**Goal:** Offline STT and TTS services running on **GPU** (shared via
time-slicing with Ollama). Language: **Spanish (Spain / es-ES)**.

### 5.1 Speech-to-Text (faster-whisper)

| Detail | Value |
|---|---|
| Library | `faster-whisper` (CTranslate2 backend, GPU-accelerated) |
| Model | `small` (244M params, ~500 MB) — best accuracy/speed for Spanish |
| Execution | **GPU** (`device="cuda"`, `compute_type="float16"`) via time-slicing |
| Language | Spanish (`language="es"`) |
| Spanish WER | ~8-10% (Common Voice benchmark) |
| API | HTTP endpoint: `POST /stt` with audio file → returns text |

```python
# POST /stt
# Content-Type: multipart/form-data
# Body: audio file (WAV or WebM)
# Response: {"text": "mensaje transcrito del operador"}
```

**Configuration:**
```python
from faster_whisper import WhisperModel
model = WhisperModel("small", device="cuda", compute_type="float16")
segments, info = model.transcribe(
    audio_path, language="es", beam_size=5,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500),
)
```

### 5.2 Text-to-Speech (Piper)

| Detail | Value |
|---|---|
| Engine | Piper TTS (ONNX Runtime) |
| Voices | `es_ES-davefx-medium` and `es_ES-sharvard-medium` (22.05kHz, ~65MB each) |
| Execution | **GPU** (ONNX Runtime CUDA provider) or CPU fallback |
| API | HTTP endpoint: `POST /tts` with text → returns audio (WAV) |

```python
# POST /tts
# Content-Type: application/json
# Body: {"text": "Respuesta del agente sintetizada"}
# Response: audio/wav binary
```

**Voice selection:** Both `davefx` (male) and `sharvard` (corpus-based)
will be tested. The best-sounding one for the demo will be selected
during implementation.

### 5.3 Service Structure

```
speech_service/
├── __init__.py
├── main.py              # FastAPI: /stt and /tts endpoints
├── stt.py               # faster-whisper wrapper
├── tts.py               # Piper wrapper
├── models/              # Pre-downloaded model files (baked into Docker image)
├── Dockerfile           # nvidia/cuda base image + models
└── requirements.txt
```

### 5.4 VRAM Budget (GPU Time-Slicing)

| Component | VRAM | Location |
|---|---|---|
| qwen2.5:7b (Ollama) | ~4.7 GB | GPU (time-slice 1) |
| Whisper `small` | ~500 MB | GPU (time-slice 2) |
| Piper TTS | ~50 MB | GPU (time-slice 2) |
| **Total VRAM** | **~5.25 GB** | **< 6 GB limit ✓** |

The workflow is sequential (STT → LLM → TTS), so these never
compete for GPU compute simultaneously. GPU time-slicing (configured
in NVIDIA device plugin, 3 replicas) allows both pods to hold a GPU
claim without conflict.

> In a production setup with multiple GPUs, each service would have
> a dedicated GPU and no time-slicing would be needed.

### 5.5 Testing

- STT: Record test audio in Spanish → verify transcription accuracy
- TTS: Send Spanish text → verify audio output is natural-sounding
- Latency: STT < 1s (GPU), TTS < 0.5s (GPU) for typical messages
- Offline: Disconnect network, verify both still work

### Acceptance Criteria

- [ ] `/stt` endpoint transcribes Spanish audio to text accurately
- [ ] `/tts` endpoint synthesises Spanish text to natural audio
- [ ] Both run fully offline (no network calls)
- [ ] Both use GPU via time-slicing (no CPU fallback needed)
- [ ] Latency acceptable for conversational use

---

## Phase 6 — Voice UI

**Goal:** Walkie-talkie web interface for operator voice interaction.

### 6.1 UI Design

Minimal, tactical-style interface:

```
┌─────────────────────────────────┐
│         BMS COMMS               │
│                                 │
│    ┌───────────────────────┐    │
│    │                       │    │
│    │   [ HOLD TO TALK ]    │    │
│    │                       │    │
│    └───────────────────────┘    │
│                                 │
│    Status: Ready                │
│    Active Case: BMS-2026-003   │
│                                 │
│    ┌───────────────────────┐    │
│    │ Agent: "Camera shows   │   │
│    │ a dark green SUV..."   │   │
│    └───────────────────────┘    │
│                                 │
│    Conversation History  ↓      │
│    ─────────────────────────    │
│    [Operator] I see a vehicle   │
│    [Agent] Creating case...     │
│    [Operator] Coordinates are.. │
│    [Agent] Surveillance shows.. │
└─────────────────────────────────┘
```

### 6.2 Interaction Flow

1. Operator holds "TALK" button → browser records audio (MediaRecorder API)
2. On release → audio blob sent to `POST /api/voice`
3. Backend: audio → STT → text
4. Backend: text → BMS API `/api/messages` → MAF workflow → response text
5. Backend: response text → TTS → audio
6. Frontend: receives audio → plays it automatically
7. Frontend: SSE updates show case/interaction in real time

### 6.3 API Endpoint

```python
@app.post("/api/voice")
async def handle_voice(audio: UploadFile):
    # 1. STT
    text = await stt_service.transcribe(audio)

    # 2. Process through agent workflow
    result = await handle_message(text)

    # 3. TTS
    audio_response = await tts_service.synthesise(result.response)

    # 4. Return audio + metadata
    return StreamingResponse(audio_response, media_type="audio/wav",
                             headers={"X-Case-Id": result.case_id})
```

### 6.4 Technology

- HTML5 MediaRecorder API for audio capture
- WebM/Opus encoding from browser → WAV conversion on backend
- Audio playback via `<audio>` element or Web Audio API
- Same static files served by FastAPI

### Acceptance Criteria

- [ ] Hold button records audio in browser
- [ ] Release sends audio to backend
- [ ] Response audio plays automatically
- [ ] Conversation history displays in real time
- [ ] Active case ID shown on screen
- [ ] Works entirely offline (after initial page load)

---

## Phase 7 — End-to-End Integration

**Goal:** Connect all components into a single working system.

### 7.1 Integration Tasks

| Task | Detail |
|---|---|
| Connect Voice UI → Speech Service | WebM audio upload → STT transcription |
| Connect Speech Service → BMS API | Transcribed text → `/api/messages` |
| Connect BMS API → MAF Workflow | Message → 3-level nested workflow |
| Connect MAF → MCP Services | Camera + Weather + BMS agents call MCP servers |
| Connect BMS API → Frontend | SSE events update dashboard live |
| Connect BMS API → TTS | Response text → audio synthesis |
| Connect TTS → Voice UI | Audio playback to operator |

### 7.2 End-to-End Test Scenario

Execute the full conversation flow:

1. Operator speaks: *"I see an unidentified vehicle near my position"*
2. STT transcribes → text sent to agents
3. Orchestrator routes to CaseManager → **case created in DB**
4. Orchestrator routes to FieldSpecialist → asks for coordinates
5. TTS synthesises response → operator hears it
6. Operator speaks coordinates
7. FieldCoordinator → ReconAgent → Camera MCP ∥ Weather MCP
8. Assessment spoken back + **logged as interaction in DB**
9. Operator requests vehicle identification
10. VehicleExpert analysis → **logged as interaction**
11. Dashboard shows full case timeline in real time

### 7.3 Error Handling

| Scenario | Handling |
|---|---|
| Ollama timeout | Retry once, then return "Service temporarily unavailable" |
| MCP service down | Agent reports tool failure, continues without data |
| DB connection lost | Queue interactions in memory, flush when reconnected |
| STT fails to transcribe | Return error to UI, operator can retry |
| Model routing error | Orchestrator fallback: ask operator to clarify |

### Acceptance Criteria

- [ ] Full scenario runs voice-to-voice without manual intervention
- [ ] All cases and interactions appear in PostgreSQL
- [ ] Dashboard updates in real time during the conversation
- [ ] Each agent response is traceable in the interaction log
- [ ] System works completely offline
- [ ] Agent handoff traces visible in Grafana (via Tempo)

---

## Phase 8 — Kubernetes Deployment

**Goal:** All components deployed to the K8s cluster via GitOps,
including the observability stack (Tempo + ServiceMonitors + dashboards).

### 8.1 Container Images

| Image | Base | Build |
|---|---|---|
| `bms-ops/bms-agents` | python:3.13-slim | MAF + agents + workflow |
| `bms-ops/bms-api` | python:3.13-slim | FastAPI + dashboard + SSE |
| `bms-ops/mcp-camera` | python:3.13-slim | MCP Camera server |
| `bms-ops/mcp-weather` | python:3.13-slim | MCP Weather server |
| `bms-ops/mcp-bms` | python:3.13-slim | MCP BMS server (PostgreSQL CRUD) |
| `bms-ops/speech-service` | nvidia/cuda:12-runtime + python | faster-whisper + Piper + Spanish models (GPU) |
| `bms-ops/bms-frontend` | python:3.13-slim* | FastAPI serving static files |

> \* Frontend may be merged into bms-api if serving static files from
> the same FastAPI app.

All images pushed to Nexus at `docker.maf.local`.

### 8.2 K8s Manifests

```
k8s/
├── shared-services/        # Shared infrastructure
│   ├── namespace.yaml
│   └── ollama.yaml          # PVC + Deployment + Service
├── bms-ops/                # BMS PoC components
│   ├── namespace.yaml
│   ├── configmap.yaml       # Shared config (OLLAMA_HOST, DB_URL, etc.)
│   ├── secrets.yaml         # DB credentials (sealed or external-secrets)
│   ├── bms-api.yaml         # API + frontend + workflow engine
│   ├── mcp-camera.yaml      # MCP Camera service
│   ├── mcp-weather.yaml     # MCP Weather service
│   ├── mcp-bms.yaml         # MCP BMS service (PostgreSQL CRUD)
│   ├── speech-service.yaml  # STT + TTS (GPU)
│   └── ingress.yaml         # bms.maf.local → bms-api
├── monitoring/              # Observability resources
│   ├── tempo.yaml           # Grafana Tempo deployment + service + datasource
│   ├── dcgm-exporter.yaml   # NVIDIA GPU metrics (VRAM, utilisation, temp)
│   ├── postgres-exporter.yaml # PostgreSQL metrics sidecar
│   ├── ollama-servicemonitor.yaml # Scrape Ollama /metrics
│   ├── servicemonitors.yaml # Per-service Prometheus scrape configs
│   └── dashboards/          # Grafana dashboard ConfigMaps
│       ├── bms-operations.json  # Agent routing, cases, handoffs
│       ├── infrastructure.json  # Ollama, GPU, PostgreSQL health
│       └── speech.json          # STT/TTS latency and errors
└── argocd-app.yaml          # GitOps application (path: k8s/bms-ops)
```

### 8.3 Service Communication (K8s DNS)

| From | To | URL |
|---|---|---|
| bms-api | Ollama | `http://ollama.shared-services.svc.cluster.local:11434` |
| bms-api | PostgreSQL | `postgresql://postgres.db.svc.cluster.local:5432/bms_ops` |
| bms-api | MCP Camera | `http://mcp-camera.bms-ops.svc.cluster.local:8090` |
| bms-api | MCP Weather | `http://mcp-weather.bms-ops.svc.cluster.local:8091` |
| bms-api | MCP BMS | `http://mcp-bms.bms-ops.svc.cluster.local:8093` |
| bms-api | Speech | `http://speech-service.bms-ops.svc.cluster.local:8092` |
| All services | Tempo (OTLP) | `http://tempo.monitoring.svc.cluster.local:4317` |
| Browser | bms-api | `https://bms.maf.local` (via ingress) |
| Browser | Grafana | `https://grafana.maf.local` (pre-existing) |

### 8.4 Resource Budget (Single Node)

| Component | CPU req/lim | RAM req/lim | GPU |
|---|---|---|---|
| Ollama | 1 / 2 | 4Gi / 6Gi | 1× (time-sliced) |
| bms-api | 500m / 1 | 512Mi / 1Gi | — |
| mcp-camera | 100m / 250m | 64Mi / 128Mi | — |
| mcp-weather | 100m / 250m | 64Mi / 128Mi | — |
| mcp-bms | 100m / 250m | 128Mi / 256Mi | — |
| speech-service | 500m / 1 | 1Gi / 2Gi | 1× (time-sliced) |
| **Total BMS** | **~2.4 / ~4.75** | **~5.7Gi / ~9.7Gi** | **2× (time-sliced from 1 physical)** |

> Verify node has sufficient CPU and RAM for these + system services.

### 8.5 Deployment Steps

1. Deploy Grafana Tempo to `monitoring` namespace
2. Deploy dcgm-exporter (GPU metrics) to `monitoring` namespace
3. Deploy postgres-exporter sidecar in `db` namespace
4. Add Tempo as Grafana datasource
5. Build and push all images to Nexus
6. Create DB, schema, and user in PostgreSQL
7. Create K8s secrets (DB credentials, registry pull secret)
8. Apply K8s manifests (or push to Gitea for ArgoCD)
9. Apply ServiceMonitors for each Python service + Ollama
10. Import Grafana dashboards (operations, infrastructure, speech)
11. Verify all pods running
12. Create ingress for `bms.maf.local`
13. End-to-end smoke test from browser
14. Verify traces appear in Grafana → Tempo
15. Verify GPU metrics appear in Grafana → Prometheus

### Acceptance Criteria

- [ ] All pods Running, no CrashLoopBackOff
- [ ] Cross-namespace DNS works (bms-ops → shared-services, bms-ops → db)
- [ ] Ingress routes to BMS frontend and API
- [ ] ArgoCD shows Synced/Healthy
- [ ] Agent traces visible in Grafana (Tempo datasource)
- [ ] Prometheus scrapes metrics from all Python services
- [ ] Full E2E test passes from browser

---

## Phase 9 — Validation & Demo

**Goal:** Prove the PoC works end-to-end with a recorded demo.

### 9.1 Validation Checklist

| # | Requirement | How to Verify |
|---|---|---|
| 1 | Voice-driven interaction | Operator speaks → system responds with audio |
| 2 | Offline execution | Disconnect internet → system still works |
| 3 | Multi-agent collaboration | Logs show L1+L2+L3 routing across 6 agents |
| 4 | MCP tool abstraction | Camera + Weather + BMS data goes through MCP servers |
| 5 | BMS persistence | Cases + interactions in PostgreSQL after demo |
| 6 | Real-time dashboard | Browser shows live updates during operation |
| 7 | K8s deployment | All components running as pods |
| 8 | GitOps | Code push to Gitea triggers ArgoCD sync |
| 9 | Deterministic sensors | Same coordinates produce same camera/weather data |
| 10 | Case lifecycle | Case OPEN → IN_PROGRESS → CLOSED visible in UI |
| 11 | Observability | Agent handoff traces visible in Grafana via Tempo |
| 12 | Metrics | All services expose /metrics, Prometheus scrapes them |

### 9.2 Demo Scenario Script

| Step | Operator Says (Spanish) | Expected Agent Behaviour |
|---|---|---|
| 1 | *"Operaciones, aquí Alpha-7. Vehículo no identificado en mi zona"* | Orchestrator → CaseManager creates case (BMS-2026-001) |
| 2 | *"Coordenadas 40.4168 Norte, 3.7038 Oeste"* | Orchestrator → FieldSpecialist → Recon (Camera ∥ Meteo via MCP) |
| 3 | *(escucha el informe)* | FieldSpecialist returns combined recon report + weather |
| 4 | *"Identificar el vehículo"* | FieldCoord → VehicleExpert provides identification |
| 5 | *"Crear caso prioridad ALTA, posible vigilancia hostil"* | CaseManager updates case priority + adds interaction |
| 6 | *"Alpha-7, fuera"* | Orchestrator closes conversation; case remains in BMS |

### 9.3 Demo Deliverables

- [ ] Screen recording of full demo (voice + dashboard + terminal logs)
- [ ] PostgreSQL query showing created cases and interactions
- [ ] `kubectl get pods` showing all components running
- [ ] ArgoCD screenshot showing Synced/Healthy
- [ ] Grafana trace screenshot showing full agent handoff chain
- [ ] Grafana dashboard screenshot showing service metrics

---

## Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R1 | MAF upstream changes break workflow builders | Medium | High | Pin to specific commit hash in `requirements.txt` |
| R2 | qwen2.5:7b fails complex tool-calling chains | Medium | High | Simplify agent instructions; add retry logic; test with phi4-mini as backup |
| R3 | 6 GB VRAM insufficient for all GPU workloads | Low | High | GPU time-slicing (3 replicas); total VRAM ~5.25 GB < 6 GB; sequential workflow avoids contention |
| R4 | MAF MCP plugin doesn't work with Ollama | Medium | Medium | Fallback: manual tool wrapper functions calling MCP via HTTP |
| R5 | Inner HITL auto-response breaks with more interactions | Medium | Medium | Increase auto-response pool; add dynamic response generation |
| R6 | Single K8s node runs out of memory | Medium | High | Monitor with Prometheus; set resource limits; all travel planner pods deleted |
| R7 | Whisper transcription inaccurate for Spanish | Low | Medium | Use `small` model (better WER than `base`); VAD filter; test with multiple speakers |
| R8 | Browser microphone permissions blocked | Low | Low | Document HTTPS requirement; use cert-manager TLS |
| R9 | PostgreSQL in `db` namespace has no capacity | Low | Medium | Create dedicated database; check existing provisioning |
| R10 | Nexus/Gitea auth issues during CI/CD | Medium | Low | Document credentials; automate image push in Makefile |

---

## Infrastructure Reference

### Cluster

| Item | Value |
|---|---|
| Master | `kube-server` (192.168.60.10) |
| K8s version | v1.35.1 (kubeadm) |
| OS | Ubuntu 24.04 |
| GPU | NVIDIA GTX 1660 Ti (6 GB VRAM) + time-slicing (3 replicas) |
| Runtime | containerd 2.2.1 |
| CNI | Flannel |
| SSH | `kiko@192.168.60.10` |

### Namespaces

| Namespace | Contents |
|---|---|
| `bms-ops` | BMS PoC components (this project) |
| `shared-services` | Ollama (GPU, LLM inference) |
| `db` | PostgreSQL |
| `argocd` | ArgoCD |
| `gitea` | Gitea |
| `nexus` | Nexus (Docker registry) |
| `monitoring` | Grafana + Prometheus |
| `ingress-nginx` | Ingress controller |
| `metallb-system` | Load balancer |
| `cert-manager` | TLS certificate management |

### Credentials (Test Cluster)

| Service | User | Password |
|---|---|---|
| SSH / Gitea | `kiko` | `Soykiko2` |
| Nexus (Docker push) | `admin` | `N3xus!Maf2026` |
| ArgoCD | (check argocd-initial-admin-secret) | — |

### DNS / Ingress

| Hostname | Service |
|---|---|
| `docker.maf.local` | Nexus Docker registry (port 8082 hosted) |
| `nexus.maf.local` | Nexus web UI |
| `gitea.maf.local` | Gitea |
| `argocd.maf.local` | ArgoCD |
| `bms.maf.local` | BMS (to be created in Phase 8) |

### Docker Image Push Command

```bash
# Build
docker build -t bms-ops/<name>:latest .

# Save + push via skopeo (from devcontainer)
docker save bms-ops/<name>:latest -o /tmp/<name>.tar
skopeo copy --dest-tls-verify=false \
  --dest-creds 'admin:N3xus!Maf2026' \
  docker-archive:/tmp/<name>.tar \
  docker://docker.maf.local/bms-ops/<name>:latest
```

### Git Push to Both Remotes

```bash
git push origin main && GIT_SSL_NO_VERIFY=1 git push gitea main
```
