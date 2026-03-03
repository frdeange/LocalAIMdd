# Offline Agentic BMS — Proof of Concept Specification

## 1. Purpose

This document defines the objectives and requirements for a Proof of
Concept that validates:

- Execution of AI agents in **fully disconnected (offline) environments**
- Multi-agent orchestration using **Microsoft Agent Framework (MAF)** with
  nested workflow patterns (HandoffBuilder, ConcurrentBuilder, Agent-as-facade)
- Voice-driven interaction between an operator and the agent platform
- Tool abstraction via **Model Context Protocol (MCP)** services
- Persistent operational logging into a **BMS (Battlefield Management System)**
- End-to-end deployment inside a **single-node Kubernetes cluster**

The objective is **NOT** production readiness. It is the technical
validation of an offline agentic architecture that can later evolve into
a production system.

---

## 2. Development & Deployment Environment

### Development Environment

| Component       | Detail                                     |
|-----------------|--------------------------------------------|
| IDE             | VS Code + DevContainer                     |
| Language        | Python 3.13                                |
| Base image      | Debian 12 (bookworm) — Linux container     |
| AI Framework    | Microsoft Agent Framework (`@main` branch) |
| LLM Runtime     | Ollama (local, GPU-accelerated)            |
| LLM Model       | `qwen2.5:7b` (4.7 GB, fits in 6 GB VRAM)  |

### Deployment Target

| Component       | Detail                                         |
|-----------------|------------------------------------------------|
| Cluster         | Kubernetes v1.35 — kubeadm, single-node        |
| GPU             | NVIDIA GTX 1660 Ti (6 GB VRAM) — device plugin + time-slicing |
| Networking      | Flannel CNI + MetalLB + ingress-nginx           |
| TLS             | cert-manager with self-signed CA (maf.local)    |
| Registry        | Nexus (docker.maf.local)                        |
| Git             | Gitea (gitea.maf.local)                         |
| GitOps          | ArgoCD (argocd.maf.local)                       |
| Database        | PostgreSQL (db namespace, already provisioned)   |
| Monitoring      | Grafana + Prometheus + Tempo (monitoring namespace) |

### Offline Requirement

The system **MUST** operate without external internet connectivity at
runtime. Model weights, container images, and all dependencies must be
pre-loaded into the cluster. Internet access is only acceptable during
the initial build/preparation phase.

---

## 3. High-Level Concept

The system simulates a battlefield operational environment composed of:

1. **BMS Platform** — persistent case tracking with real-time UI
2. **Operator Voice Interface** — walkie-talkie style push-to-talk web UI
3. **Offline AI Agent Platform** — MAF-based multi-agent orchestration
4. **External systems via MCP** — Camera, Weather, and BMS as MCP tool servers

The operator communicates using voice commands. Speech is transcribed
locally (STT), processed by the agent platform, and responses are
synthesised back to audio (TTS). All agent activity is logged into the
BMS in real time.

---

## 4. System Architecture

```
Operator (Field)                       Command Post
      │                                     │
      ▼                                     ▼
┌─────────────────────┐   ┌─────────────────────┐
│  Walkie-Talkie UI    │   │  BMS Dashboard        │
│  (push-to-talk)      │   │  (cases + timeline)   │
└────────┬────────────┘   └────────┬────────────┘
         │ audio                    │ SSE (live updates)
         ▼                          │
┌─────────────────────┐          │
│  Speech Service      │          │
│  STT + TTS (GPU)     │          │
└────────┬────────────┘          │
         │ text                     │
         ▼                          ▼
┌─────────────────────────────────────────────────────────┐
│  BMS API (FastAPI)                                       │
│  ├── /api/voice — operator audio in/out                  │
│  ├── /api/messages — operator text (fallback)             │
│  ├── /api/cases — case queries (dashboard)                │
│  ├── /api/stream — SSE live updates (dashboard)            │
│  └── Invokes MAF workflow                                │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  MAF Agent Platform — 3-Level Nested Architecture        │
│                                                          │
│  L3  HandoffBuilder "bms_operations"                     │
│  │   Orchestrator (start) ←→ CaseManager                │
│  │   Orchestrator ←→ FieldSpecialist (facade)           │
│  │                                                       │
│  L2  └─ HandoffBuilder "field_operations"                │
│  │      FieldCoord (start) ←→ VehicleExpert             │
│  │      FieldCoord ←→ ReconAgent (facade)               │
│  │                                                       │
│  L1  └─ ConcurrentBuilder "recon"                        │
│         CameraAgent ∥ MeteoAgent                         │
└────────┬──────────────┬──────────────┬──────────────────┘
         │ MCP          │ MCP          │ MCP
         ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ MCP Camera   │ │ MCP Weather  │ │ MCP BMS Service      │
│ (simulated)  │ │ (simulated)  │ │ (PostgreSQL CRUD)    │
└──────────────┘ └──────────────┘ └──────────────────────┘
```

**All agent access to external systems goes through MCP.** This
includes sensors (Camera, Weather) AND the BMS database. Agents never
call REST APIs or databases directly — they use MCP tools exclusively.

All meaningful agent outputs **MUST** be persisted into the BMS as
interaction records.

---

## 5. Core Components

### 5.1 BMS Platform

A simplified operational management system providing:

- **PostgreSQL database** storing cases and interactions
- **MCP BMS Service** — MCP tool server exposing case CRUD operations to agents
- **REST API** (FastAPI) for operator message ingestion, SSE streaming, and frontend serving
- **Web dashboard** displaying live case updates via SSE/WebSocket

> **Architectural principle:** Agents interact with the BMS exclusively
> through the MCP BMS Service. The REST API handles operator-facing
> concerns (message ingestion, voice pipeline, SSE streaming, dashboard).
> The MCP BMS Service handles agent-facing concerns (case CRUD).

#### Data Model

```
Case
├── case_id          (format: BMS-YYYY-NNN)
├── created_at       (ISO 8601 timestamp)
├── status           (OPEN | IN_PROGRESS | CLOSED)
├── priority         (LOW | MEDIUM | HIGH | CRITICAL)
├── summary          (initial operator message)
└── interactions[]

Interaction
├── interaction_id
├── case_id          (FK → Case)
├── timestamp
├── agent_name       (which agent produced this)
├── message          (agent output text)
└── metadata         (JSON — coordinates, tool results, etc.)
```

Every agent response that reaches the operator **MUST** generate an
interaction record. Internal routing messages (handoffs) are optional.

---

### 5.2 Operator Interfaces

Two separate web interfaces for different user profiles:

#### Walkie-Talkie UI (Field Operator)

Used by the **field operator** in the area of operations:

- Push-to-talk button (hold to record, release to send)
- Audio recording sent to backend for STT transcription
- Agent text responses synthesised to audio via TTS
- Audio playback to operator
- Visual indicator of agent processing state
- No keyboard interaction required

#### BMS Dashboard (Command Post)

Used by **command staff** at the advanced command post or HQ:

- List of active cases with status and priority
- Case detail view with full interaction timeline
- Live updates via SSE (new cases/interactions appear automatically)
- Read-only view — command staff observes, field operator drives

> In the PoC there are no user profiles, authentication, or roles.
> Both interfaces are open and can be accessed by anyone on the network.
> The separation is conceptual (field vs. command post).

---

### 5.3 Speech Layer (Offline)

All speech processing must run locally without internet.
The demo language is **Spanish (Spain / es-ES)**.

#### Speech-to-Text (STT)

- **faster-whisper** (CTranslate2 backend) — Whisper-compatible, GPU-accelerated
- Model: `small` (244M params, ~500 MB) — best accuracy/speed balance for Spanish
- Execution: **GPU** via NVIDIA time-slicing (shared with Ollama)
- Spanish WER: ~8-10% (Common Voice benchmark)
- VAD filter enabled to avoid hallucinations on silence

#### Text-to-Speech (TTS)

- **Piper TTS** — lightweight, fast, offline, ONNX-based
- Voice models: `es_ES-davefx-medium` and `es_ES-sharvard-medium` (22.05kHz)
- Execution: **GPU** (ONNX Runtime CUDA) or CPU fallback
- Both voices will be evaluated during implementation; best one selected for demo

#### GPU Sharing Strategy

The workflow is sequential: STT → LLM → TTS. These never run
concurrently. NVIDIA GPU time-slicing (device plugin config, 3
replicas) allows multiple pods to share the same physical GPU:

| Component | VRAM | Coexistence |
|---|---|---|
| qwen2.5:7b (Ollama) | ~4.7 GB | Always loaded |
| Whisper `small` | ~500 MB | 4.7 + 0.5 = **5.2 GB ✓** |
| Piper TTS | ~50 MB | Negligible |
| **Total** | **~5.25 GB** | **< 6 GB ✓** |

> In a production environment with multiple GPUs, each service would
> have a dedicated GPU and concurrency would be handled naturally.

---

## 6. Agent Architecture

All agents are implemented using **Microsoft Agent Framework (MAF)**.

### Validated Orchestration Patterns

| Pattern | MAF Builder | Usage |
|---|---|---|
| **Sequential routing with HITL** | `HandoffBuilder` | L2 (Field), L3 (Operations) |
| **Parallel fan-out / fan-in** | `ConcurrentBuilder` | L1 (Recon: Camera ∥ Meteo) |
| **Workflow nesting** | Agent-as-facade | Wraps inner workflow in a real `Agent` with tool function |

> **Known constraint:** `WorkflowAgent.as_agent()` is NOT compatible
> with `HandoffBuilder`. The Agent-as-facade pattern (real Agent + tool
> that internally runs the sub-workflow) is the validated workaround.

### 6.1 Orchestrator Agent (L3 — start)

Top-level decision maker.

- Interprets operator intent
- Routes to CaseManager (case operations) or FieldSpecialist (field ops)
- Only agent exposing real human-in-the-loop (HITL) to the operator

### 6.2 Case Management Agent (L3)

Creates and updates BMS cases.

- Creates case from initial operator report
- Updates existing case with new intel
- Calls **MCP BMS Service** tools for persistence (`create_case`, `update_case`, `add_interaction`, `get_case`)
- Maintains structured operational history

### 6.3 Field Specialist (L3 — facade → L2)

Facade agent wrapping the Level 2 field operations workflow.

- Delegates to FieldCoordinator → ReconAgent / VehicleExpert
- Auto-responds to inner HITL requests (L2 runs autonomously)
- Returns aggregated field assessment to Orchestrator

### 6.4 Field Coordinator (L2 — start)

Routes tasks within field operations.

- Coordinates/surveillance requests → ReconAgent
- Vehicle description/identification → VehicleExpert
- Aggregates sub-results

### 6.5 Recon Agent (L2 — facade → L1)

Facade agent wrapping the Level 1 concurrent reconnaissance workflow.

- Triggers CameraAgent ∥ MeteoAgent in parallel
- Returns combined recon report

### 6.6 Camera Agent (L1)

Simulates camera sensor via **MCP tool call**.

- Calls MCP Camera Service with coordinates
- Receives simulated image/observation data
- Reports surveillance findings

### 6.7 Meteo Agent (L1)

Provides weather assessment via **MCP tool call**.

- Calls MCP Weather Service with coordinates
- Receives simulated weather conditions
- Reports operational impact assessment

### 6.8 Vehicle Expert (L2)

Analyses vehicle characteristics.

- Identifies vehicle type, make, model from descriptions
- Rates identification confidence
- Provides tactical context

---

## 7. MCP Services

All external system access from agents **MUST** go through MCP servers.
These are not simple scripts — they are proper MCP tool servers that
agents call via the Model Context Protocol. This applies to simulated
sensors (Camera, Weather) and to the BMS database (case management).

### Technology

All MCP servers are built with **FastMCP ≥ 3.1**
([gofastmcp.com](https://gofastmcp.com)).

| Aspect | Detail |
|---|---|
| Framework | FastMCP v3.1+ |
| Transport | SSE (for K8s network access) or stdio (for local dev) |
| Telemetry | Built-in — FastMCP exposes OpenTelemetry traces automatically |
| Language | Python 3.13 |

### 7.1 MCP Camera Service

| Field | Value |
|---|---|
| Transport | **streamable-http** |
| Tool name | `get_camera_feed` |
| Input | `coordinates` (lat, lon), `zoom_level` |
| Output | Simulated observation (text description + metadata) |
| Behaviour | Pretends to reposition camera; returns pre-defined observation data based on coordinate sector |

### 7.2 MCP Weather Service

| Field | Value |
|---|---|
| Transport | **streamable-http** |
| Tool name | `get_weather_report` |
| Input | `coordinates` (lat, lon) |
| Output | `temperature`, `conditions`, `wind_speed`, `visibility_km`, `risk_level` |
| Behaviour | Returns deterministic mock data based on coordinate sector |

Data is fully mocked — the PoC validates the MCP integration pattern,
not real sensor data.

### 7.3 MCP BMS Service

| Field | Value |
|---|---|
| Transport | **streamable-http** |
| Tool: `create_case` | Input: `summary`, `priority`, `coordinates` → Output: `case_id` |
| Tool: `update_case` | Input: `case_id`, `status`, `priority` → Output: confirmation |
| Tool: `add_interaction` | Input: `case_id`, `agent_name`, `message` → Output: `interaction_id` |
| Tool: `get_case` | Input: `case_id` → Output: case with all interactions |
| Tool: `list_cases` | Input: `status` (optional filter) → Output: case list |
| Behaviour | Real CRUD against PostgreSQL. This is NOT simulated — it persists real data. |

The MCP BMS Service is the **only** path for agents to read/write BMS
data. The BMS API (FastAPI) also queries the same PostgreSQL for the
dashboard and SSE streaming, but agents never call the REST API directly.

---

## 8. Conversation Flow

### Step 1 — Operator Input
Operator speaks into walkie-talkie UI.
Example: *"I see an unidentified vehicle near my position."*

### Step 2 — Speech Processing
Audio → STT (Whisper) → text sent to BMS API.

### Step 3 — Case Creation
Orchestrator → CaseManager: create BMS case (persisted to DB).

### Step 4 — Information Gathering
Orchestrator → FieldSpecialist → FieldCoordinator asks for coordinates.
Response relayed to operator via TTS.

### Step 5 — Sensor Activation
Operator provides coordinates. FieldCoordinator dispatches:
1. ReconAgent → CameraAgent (MCP) ∥ MeteoAgent (MCP) — concurrent
2. Results aggregated by ReconAgent → FieldCoordinator

### Step 6 — Initial Assessment
FieldSpecialist returns combined assessment to Orchestrator.
Result: spoken back to operator + logged to BMS.

### Step 7 — Advanced Analysis (on request)
If operator requests vehicle identification:
FieldCoordinator → VehicleExpert → analysis returned.

### Step 8 — Continuous Logging
Every agent response reaching the operator generates a BMS interaction.
Case status updated throughout the conversation lifecycle.

---

## 9. Offline Constraints

| Allowed | NOT Allowed |
|---|---|
| Local LLM models (Ollama + qwen2.5:7b) | Cloud inference (OpenAI, Azure, etc.) |
| Local STT/TTS models | External speech APIs |
| Simulated MCP services | Real external sensor APIs |
| Local PostgreSQL | Cloud databases |
| Pre-built container images in Nexus | Runtime pulls from Docker Hub |
| Pre-cloned Git repos in Gitea | Runtime clones from GitHub |

Internet is acceptable **only** during the build/preparation phase
(downloading models, building images, pulling dependencies).

---

## 10. Kubernetes Deployment

All components deployed in the `bms-ops` namespace (except shared
infrastructure).

### Target Pod Layout

| Pod / Deployment | Namespace | GPU | Purpose |
|---|---|---|---|
| `ollama` | shared-services | Yes (1× time-sliced) | LLM inference (qwen2.5:7b) |
| `bms-agents` | bms-ops | No | MAF agent platform + BMS API |
| `mcp-camera` | bms-ops | No | MCP Camera tool server |
| `mcp-weather` | bms-ops | No | MCP Weather tool server |
| `mcp-bms` | bms-ops | No | MCP BMS tool server (PostgreSQL CRUD) |
| `bms-frontend` | bms-ops | No | BMS Dashboard (command post) + Walkie-Talkie UI (field) |
| `speech-service` | bms-ops | Yes (1× time-sliced) | faster-whisper STT + Piper TTS (GPU) |
| `postgresql` | db | No | Shared database (already exists) |

> GPU time-slicing configured via NVIDIA device plugin (3 replicas per
> physical GPU). Ollama and speech-service each claim 1 time-sliced GPU.

### Infrastructure (pre-existing)

- ArgoCD (GitOps sync from Gitea)
- Nexus (container image registry)
- Gitea (Git repository mirror)
- cert-manager + ingress-nginx (TLS + routing)
- MetalLB (load balancer)
- Grafana + Prometheus + Alertmanager (monitoring)
- Grafana Tempo (distributed tracing)

---

## 11. Observability & Monitoring

All services **MUST** be observable. The PoC uses a three-pillar
approach: metrics, distributed traces, and logs.

### 11.1 Stack

| Pillar | Tool | Namespace | Purpose |
|---|---|---|---|
| **Metrics** | Prometheus | monitoring | Scrape application and system metrics |
| **Tracing** | Grafana Tempo | monitoring | Distributed trace storage and query |
| **Dashboards** | Grafana | monitoring | Visualisation (`grafana.maf.local`) |
| **Alerting** | Alertmanager | monitoring | Alert routing (pre-existing) |
| **Instrumentation** | OpenTelemetry SDK | (in-app) | Automatic span and metric generation |

> Prometheus, Grafana, and Alertmanager are already running in the
> cluster (kube-prometheus-stack). Tempo needs to be deployed.

### 11.2 Telemetry Sources

Three components generate OpenTelemetry traces **automatically**:

| Source | What It Traces |
|---|---|
| **MAF (Microsoft Agent Framework)** | Agent invocations, handoff routing, LLM calls, tool execution |
| **FastMCP (MCP servers)** | Tool call latency, invocation counts, input/output |
| **FastAPI (BMS API)** | HTTP request handling, SSE streaming, endpoint latency |

All traces are exported via **OTLP (gRPC)** to Grafana Tempo.

```
MAF agents (auto-traces) ───┐
FastMCP servers (auto-traces) ─┼──→ OTLP exporter ──→ Tempo ──→ Grafana
FastAPI (auto-instrumented) ──┘
```

### 11.3 What Gets Monitored

**Every component** in the system must be monitored. No blind spots.

| Layer | Metrics (Prometheus) | Traces (Tempo) | How |
|---|---|---|---|
| **MAF Agents** | — | Handoff chain, tool calls, LLM latency | MAF built-in OTel spans |
| **MCP Services** | Tool call count, error rate | Per-tool invocation spans | FastMCP built-in telemetry |
| **BMS API** | HTTP request rate/latency/errors | Request → workflow → response | `opentelemetry-instrumentation-fastapi` |
| **Speech Service** | STT/TTS latency histograms, error rate | Per-transcription / per-synthesis spans | Custom OTel spans + Prometheus metrics |
| **Frontend (Web)** | Page load time, JS errors, WebSocket health | — | Prometheus client-side metrics via `/metrics` endpoint |
| **Ollama** | Inference latency, tokens/s, model info | — | Ollama native `/metrics` endpoint (Prometheus format) |
| **PostgreSQL** | Connections, query latency, rows, locks, disk | — | `prometheus-postgres-exporter` sidecar |
| **GPU** | VRAM usage, GPU utilisation, temperature | — | `dcgm-exporter` (NVIDIA DCGM) |
| **Kubernetes** | Pod/node/container resources, restarts | — | kube-prometheus-stack (pre-existing) |

### 11.4 Agent Tracing Example

A single operator message produces a distributed trace showing:

```
BMS API: POST /api/messages
└─ MAF L3: Orchestrator
   ├─ handoff → CaseManager
   │  └─ MCP BMS: create_case (FastMCP auto-span)
   └─ handoff → FieldSpecialist (facade)
      └─ MAF L2: FieldCoordinator
         └─ handoff → ReconAgent (facade)
            └─ MAF L1: ConcurrentBuilder
               ├─ CameraAgent → MCP Camera: get_camera_feed
               └─ MeteoAgent → MCP Weather: get_weather_report
```

### 11.5 Kubernetes Integration

- **ServiceMonitors** per Python service (auto-discovered by Prometheus)
- **PodMonitors** where ServiceMonitors are not applicable
- **dcgm-exporter** DaemonSet for GPU metrics (VRAM, utilisation, temp)
- **postgres-exporter** sidecar for PostgreSQL metrics
- Custom **Grafana dashboards**:
  - BMS Operations: agent routing, case lifecycle, handoff counts
  - Infrastructure: Ollama inference, GPU stats, PostgreSQL health
  - Speech: STT/TTS latency, error rate, model load times
- All Python services expose `/metrics` (Prometheus format)
- All Python services export traces via OTLP (gRPC) to Tempo

---

## 12. Known Technical Constraints

| Constraint | Impact | Mitigation |
|---|---|---|
| MAF bug #4402 — `HandoffBuilder` leaks kwargs to Ollama client | `TypeError` at runtime | Monkey-patch in `src/patch_ollama.py` |
| `WorkflowAgent.as_agent()` incompatible with `HandoffBuilder` | Cannot nest workflows directly | Agent-as-facade pattern (validated) |
| qwen2.5:7b tool-calling not always reliable | Routing may fail on complex prompts | Detailed agent instructions + retry logic |
| 6 GB VRAM shared across all GPU workloads | Models must coexist in VRAM | GPU time-slicing (3 replicas); total VRAM ~5.25 GB < 6 GB |
| Single K8s node | No HA, all pods compete for resources | Acceptable for PoC |
| Inner HandoffBuilder requires HITL | L2 workflow blocks waiting for human input | Auto-response mechanism in facade tool |

---

## 13. Expected PoC Outcomes

The PoC **MUST** demonstrate:

1. **Voice-driven agent orchestration** — operator speaks, agents act
2. **3-level nested multi-agent collaboration** — HandoffBuilder + ConcurrentBuilder + facade pattern
3. **MCP-based tool abstraction** — Camera, Weather, and BMS as FastMCP server tools
4. **Offline AI execution** — all inference local via Ollama
5. **Persistent operational logging** — every agent action stored in BMS (PostgreSQL)
6. **Real-time dashboard** — live case/interaction updates in web UI
7. **Kubernetes deployment** — all components containerised and managed via GitOps
8. **Full observability** — distributed traces of agent handoffs and MCP calls visible in Grafana
