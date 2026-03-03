# Offline Agentic BMS — PoC

Multi-agent Battlefield Management System powered by
[Microsoft Agent Framework (MAF)](https://github.com/microsoft/agent-framework),
running fully offline on a single-node Kubernetes cluster with local LLM
inference via [Ollama](https://ollama.com).

## Architecture

```
Field Operator           Command Post (HQ)
      │                        │
      ▼                        ▼
┌─────────────────┐  ┌─────────────────┐
│ Walkie-Talkie │  │ BMS Dashboard   │
│ (voice I/O)   │  │ (cases + live)  │
└────────┬────────┘  └────────┬────────┘
         │ audio          │ SSE
         ▼                ▼
┌─────────────────┐  ┌─────────────────────────┐
│ Speech Service  │─▶│ BMS API (FastAPI)          │
│ STT + TTS (GPU) │  │ /voice, /cases, /stream   │
└─────────────────┘  └──────────┬──────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │ MAF Agent Platform (3 levels) │
                │ L3: Orchestrator ←→ CaseManager / FieldSpecialist │
                │ L2: FieldCoord ←→ ReconAgent / VehicleExpert      │
                │ L1: CameraAgent ∥ MeteoAgent (concurrent)        │
                └──────┬──────────┬──────────┬─┘
                       │ MCP      │ MCP      │ MCP
                       ▼          ▼          ▼
               ┌────────┐ ┌────────┐ ┌──────────┐
               │Camera   │ │Weather │ │ BMS      │  ← All FastMCP v3.1+
               │(mock)   │ │(mock)  │ │(Postgres)│
               └────────┘ └────────┘ └──────────┘
```

All external system access from agents goes through **MCP** (Model
Context Protocol). MCP servers built with **FastMCP ≥ 3.1**.

## Tech Stack

| Component | Technology |
|---|---|
| AI Framework | Microsoft Agent Framework (MAF) |
| LLM | Ollama + qwen2.5:7b (GPU) |
| MCP Servers | FastMCP ≥ 3.1 |
| STT | faster-whisper (GPU, Spanish es-ES) |
| TTS | Piper TTS (GPU, Spanish es-ES voices) |
| API | FastAPI |
| Database | PostgreSQL |
| Frontend | HTML + SSE (walkie-talkie + dashboard) |
| Observability | Prometheus + Grafana Tempo + Grafana |
| K8s | kubeadm v1.35, single-node, GPU time-slicing |
| GitOps | ArgoCD + Gitea + Nexus |

## Project Structure

```
├── docs/                    # PoC specification and implementation plan
├── src/                     # Agent core (MAF workflows + agents)
│   ├── agents/              # 6 agent factories
│   ├── workflows/           # 3-level nested workflow builders
│   ├── config.py            # Environment-driven settings
│   ├── client.py            # Ollama client factory
│   ├── patch_ollama.py      # MAF bug #4402 workaround
│   └── runner.py            # CLI entry point (interactive + demo)
├── mcp_services/            # FastMCP servers (Camera, Weather, BMS)
├── bms_api/                 # BMS REST API (FastAPI)
├── speech_service/          # STT + TTS service
├── frontend/                # Web interfaces
│   ├── walkie_talkie/       # Field operator — push-to-talk voice UI
│   └── bms_dashboard/       # Command post — cases + live timeline
├── k8s/                     # Kubernetes manifests
│   ├── shared-services/     # Ollama deployment
│   ├── bms-ops/             # BMS application resources
│   └── monitoring/          # Tempo, ServiceMonitors, dashboards
├── prototypes/              # MAF pattern validation scripts (reference)
├── Dockerfile               # Agent core container image
├── docker-compose.yml       # Local dev (Ollama GPU/CPU)
└── requirements.txt         # Python dependencies
```

## Quick Start (Local Dev)

```bash
# 1. Start Ollama
docker compose --profile gpu up -d

# 2. Pull model
docker exec bms-ollama ollama pull qwen2.5:7b

# 3. Run BMS demo
python -m src --demo
```

## Documentation

- [PoC Specification](docs/OFFLINE_AGENTIC_BMS_POC.md) — objectives, requirements, architecture
- [Implementation Plan](docs/POC_PLAN.md) — detailed phased plan with acceptance criteria

## Kubernetes Cluster

| Namespace | Purpose |
|---|---|
| `shared-services` | Ollama (GPU, LLM inference) |
| `bms-ops` | BMS application services |
| `db` | PostgreSQL |
| `monitoring` | Prometheus, Grafana, Tempo, Alertmanager |
| `argocd` | GitOps (ArgoCD) |
| `gitea` | Git repository (Gitea) |
| `nexus` | Container registry (Nexus) |
