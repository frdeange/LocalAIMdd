# Telemetry Guide

## Overview

This project uses **OpenTelemetry** for observability, exporting traces, metrics,
and structured logs to the **.NET Aspire Dashboard** via OTLP gRPC.

The Microsoft Agent Framework (MAF) provides built-in instrumentation through
`configure_otel_providers()`, which automatically creates spans for:

- Agent invocations
- LLM model calls
- Tool executions (including MCP)

Custom business spans in `src/telemetry.py` add workflow-level and agent-level
timing, plus MCP tool-call counters.

## Architecture

```
Docker Network
┌──────────────────────┐     gRPC     ┌──────────────────────┐
│  FastAPI API          │ ──────────→  │  Aspire Dashboard    │
│  (travel-planner-api)│   internal   │  :18888 (UI)         │
│  + OTel auto-instr.  │              │  :18889 (OTLP gRPC)  │
│  :8000               │              │  :18890 (OTLP HTTP)  │
└──────────────────────┘              └──────────────────────┘
                                                ▲
                                                │ gRPC
MCP Server Container                            │ (Docker internal)
┌──────────────────────┐     gRPC               │
│  FastMCP 3.0         │ ──────────→ aspire-dashboard:18889
│  + OTel auto-instr.  │
│  (travel-mcp-tools)  │
│  :8090               │
└──────────────────────┘
```

- **API → Aspire**: Docker internal network (`aspire-dashboard:18889`)
- **MCP → Aspire**: Docker internal network (`aspire-dashboard:18889`)
- **External access**: Port 4317 mapped to container port 18889
- Both services appear independently in the Aspire Dashboard UI

## Setup Checklist

### 1. Install the OTLP Exporter Package

The `opentelemetry-exporter-otlp-proto-grpc` package is an **optional** dependency
of the Agent Framework. Without it, `configure_otel_providers()` silently falls back
to no-op exporters and you will see **no data** in the dashboard.

```bash
pip install opentelemetry-exporter-otlp-proto-grpc
```

This package is listed in `requirements.txt`, so `pip install -r requirements.txt`
will install it. But if you manually install packages, don't skip this one.

### 2. Environment Variables Are Set Before Startup

The API server runs inside Docker, where environment variables are set via
`docker-compose.yml` (`environment:` section). The `opentelemetry-instrument`
CLI wrapper reads these at startup, so they are always available.

For local development outside Docker, create a `.env` file and export vars:

```bash
cp .env.example .env
# source or use python-dotenv to load
```

### 3. Call `shutdown_telemetry()` Before Process Exit

MAF's `configure_otel_providers()` creates a `BatchSpanProcessor` that buffers
spans and exports them in the background. If your process exits before the buffer
is flushed, **spans are lost**.

Always call `shutdown_telemetry()` (from `src/telemetry.py`) after the workflow
completes:

```python
from src.telemetry import setup_telemetry, shutdown_telemetry

setup_telemetry()
# ... run workflow ...
shutdown_telemetry()  # flushes pending spans/metrics and shuts down providers
```

The function calls `force_flush(timeout_millis=5000)` followed by `shutdown()` on
both the `TracerProvider` and `MeterProvider`.

### 4. Start the Aspire Dashboard

```bash
docker compose up -d
```

Then open [http://localhost:18888](http://localhost:18888) to view:

- **Traces**: All spans from agent invocations, model calls, and custom business spans
- **Metrics**: `workflow.duration`, `agent.duration`, `mcp.tool_calls` histograms/counters
- **Structured Logs**: Python logging output captured by the OTel log bridge

## Environment Variables

### API Server (Docker container)

| Variable | Value | Purpose |
|----------|-------|--------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://aspire-dashboard:18889` | Aspire via Docker internal network |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | Transport protocol |
| `OTEL_SERVICE_NAME` | `travel-planner-api` | Service name in telemetry data |

The MCP server container uses its own set of OTEL variables (configured in `docker-compose.yml`):

| Variable | Value | Purpose |
|----------|-------|---------|
| `OTEL_SERVICE_NAME` | `travel-mcp-tools` | MCP server service name |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://aspire-dashboard:18889` | Aspire via Docker internal network |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | Transport protocol |

> **Note**: Use `OTEL_EXPORTER_OTLP_ENDPOINT` (base endpoint) rather than
> signal-specific variables like `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`. The base
> endpoint applies to all three signals (traces, metrics, logs), which is what
> Aspire Dashboard expects.

## Custom Spans and Metrics

### Workflow Span

```python
from src.telemetry import trace_workflow

with trace_workflow("travel_planner", user_query) as span:
    # ... execute workflow ...
    span.set_attribute("custom.key", "value")
```

Automatically records: `workflow.name`, `workflow.input`, `workflow.duration_s`.

### Agent Span

```python
from src.telemetry import trace_agent

with trace_agent("researcher", custom_attr="value") as span:
    # ... invoke agent ...
```

Automatically records: `agent.name`, `agent.duration_s`, plus any custom attributes.

### MCP Tool Call Counter

```python
from src.telemetry import record_mcp_tool_call

record_mcp_tool_call("get_weather", "http://localhost:8090/mcp")
```

Increments the `mcp.tool_calls` counter with `tool.name` and `mcp.server_url` labels.

## MCP Server Telemetry

The MCP server (FastMCP) runs in a Docker container with **auto-instrumentation**
enabled. No code changes to `server.py` are needed — all tracing is handled by
the `opentelemetry-instrument` CLI wrapper and FastMCP's native OTel API calls.

### How It Works

1. **`opentelemetry-distro`** + **`opentelemetry-exporter-otlp`** are installed in
   the container (via `mcp_server/requirements.txt`)
2. **`opentelemetry-bootstrap -a install`** runs at build time, auto-detecting
   Starlette and uvicorn and installing their instrumentations
3. The Dockerfile's `CMD` uses `opentelemetry-instrument python server.py` instead
   of plain `python server.py`
4. Environment variables in `docker-compose.yml` configure the exporter:
   - `OTEL_SERVICE_NAME=travel-mcp-tools`
   - `OTEL_EXPORTER_OTLP_ENDPOINT=http://aspire-dashboard:18889` (Docker internal network)
   - `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`

### What Gets Traced

FastMCP creates spans following [MCP semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/):

| Span Name | Example |
|-----------|---------|
| `tools/call {name}` | `tools/call get_weather` |
| `resources/read {uri}` | `resources/read config://db` |
| `prompts/get {name}` | `prompts/get greeting` |

Each span includes attributes like `rpc.system=mcp`, `rpc.service=TravelTools`,
`fastmcp.component.type=tool`, and `fastmcp.component.key=tool:get_weather`.

### Distributed Tracing

When the orchestrator's WeatherAnalyst agent calls the MCP server over HTTP, the
HTTP client propagates a W3C `traceparent` header. The MCP server's auto-instrumented
Starlette stack extracts this context, so MCP tool spans appear as **children** of
the orchestrator's agent spans in the Aspire Dashboard trace view.

This gives end-to-end visibility: `workflow → agent → HTTP request → MCP tool execution`.

### Adding Telemetry to New Services

When adding new services to the project, follow this pattern:

1. Add `opentelemetry-distro` and `opentelemetry-exporter-otlp` to the service's
   `requirements.txt`
2. Run `opentelemetry-bootstrap -a install` in the Dockerfile
3. Use `opentelemetry-instrument` as the CMD entrypoint wrapper
4. Set `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`, and
   `OTEL_EXPORTER_OTLP_PROTOCOL` via docker-compose environment variables
5. Point the endpoint to `http://aspire-dashboard:18889` (Docker internal network)

This ensures every service in the ecosystem reports to the same Aspire Dashboard
instance with consistent configuration.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No data in Aspire Dashboard | `load_dotenv()` not called before MAF imports | Move `load_dotenv()` to the top of `main.py`, before any `from agent_framework` imports |
| No data in Aspire Dashboard | `opentelemetry-exporter-otlp-proto-grpc` not installed | `pip install opentelemetry-exporter-otlp-proto-grpc` |
| Intermittent missing spans | Process exits before `BatchSpanProcessor` flushes | Call `shutdown_telemetry()` before exit |
| Connection refused on port 4317 | Aspire Dashboard not running | `docker compose up -d` |
| UNIMPLEMENTED errors for metrics/logs | Backend only supports traces (e.g., Jaeger) | Switch to Aspire Dashboard which supports all three signals |
| MCP server spans not visible | MCP container can't reach Aspire | Check `OTEL_EXPORTER_OTLP_ENDPOINT` in docker-compose uses `aspire-dashboard:18889` (Docker network) |
| MCP spans not linked to agent spans | Trace context not propagated | Ensure `opentelemetry-instrument` is used (auto-instruments HTTP server to extract `traceparent`) |

## Why Aspire Dashboard Instead of Jaeger?

Jaeger only supports **traces**. When the Agent Framework exports metrics and logs
alongside traces (all via OTLP), Jaeger returns `UNIMPLEMENTED` errors for those
signals. The Aspire Dashboard accepts **all three OTLP signals** in a single
container, providing a complete observability view without error noise.
