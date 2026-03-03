"""
BMS API — Prometheus Metrics
=============================
Application-level metrics exposed at /metrics for Prometheus scraping.
Also provides /api/frontend-metrics for client-side telemetry ingestion.
"""

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# ── API Metrics ───────────────────────────────────────────────

api_requests_total = Counter(
    "bms_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"],
)

api_request_duration = Histogram(
    "bms_api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

sse_active_connections = Gauge(
    "bms_sse_active_connections",
    "Number of active SSE connections",
)

# ── Case Metrics ──────────────────────────────────────────────

cases_total = Gauge(
    "bms_cases_total",
    "Total number of cases",
    ["status"],
)

interactions_total = Counter(
    "bms_interactions_total",
    "Total interactions logged",
    ["agent_name"],
)

# ── Frontend Metrics (received from JS) ──────────────────────

frontend_page_loads = Counter(
    "bms_frontend_page_loads_total",
    "Dashboard page load events",
)

frontend_errors = Counter(
    "bms_frontend_errors_total",
    "Frontend JavaScript errors",
    ["type"],
)

frontend_sse_reconnects = Counter(
    "bms_frontend_sse_reconnects_total",
    "SSE reconnection events from dashboard",
)

frontend_page_load_duration = Histogram(
    "bms_frontend_page_load_seconds",
    "Dashboard page load time in seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)
