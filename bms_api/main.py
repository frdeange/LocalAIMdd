"""
BMS API — FastAPI Application
==============================
REST API for the BMS Operations PoC.

Responsibilities:
- /api/cases        — read-only case listing (for dashboard)
- /api/cases/{id}   — case detail with interactions (for dashboard)
- /api/stream       — SSE live updates (for dashboard)
- /api/messages     — operator text input → MAF workflow → response
- /api/health       — health check

Agents write to the DB via MCP BMS (not this API).
This API reads from the same DB for the dashboard.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# ── Telemetry (must be before FastAPI import for proper instrumentation) ──
from bms_api.telemetry import configure_telemetry

configure_telemetry()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from bms_api.config import API_HOST, API_PORT
from bms_api.db import get_pool, close_pool
from bms_api.schemas import (
    CaseDetail,
    CaseListResponse,
    CaseSummary,
    InteractionOut,
    OperatorMessage,
    MessageResponse,
)

logger = logging.getLogger(__name__)


# ── SSE broadcast channel ────────────────────────────────────
# Simple in-memory pub/sub for SSE. In production, use Redis pub/sub.
_sse_subscribers: list[asyncio.Queue] = []


def _broadcast_sse(event: str, data: dict) -> None:
    """Push an SSE event to all connected subscribers."""
    payload = {"event": event, "data": json.dumps(data)}
    for q in _sse_subscribers:
        q.put_nowait(payload)


# ── Lifespan ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to DB
    pool = await get_pool()
    logger.info("BMS API started — DB pool ready")

    # Start the SSE poll task (watches for new interactions)
    poll_task = asyncio.create_task(_poll_new_interactions())

    yield

    # Shutdown
    poll_task.cancel()
    await close_pool()
    logger.info("BMS API stopped")


app = FastAPI(
    title="BMS Operations API",
    version="0.1.0",
    description="REST API for the Battlefield Management System PoC",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Health check."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok", "service": "bms-api"}


# ── Cases (read-only for dashboard) ──────────────────────────

@app.get("/api/cases", response_model=CaseListResponse)
async def list_cases(status: str | None = None):
    """List all cases, optionally filtered by status."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT case_id, status, priority, summary, created_at, updated_at "
                "FROM cases WHERE status = $1 ORDER BY created_at DESC",
                status.upper(),
            )
        else:
            rows = await conn.fetch(
                "SELECT case_id, status, priority, summary, created_at, updated_at "
                "FROM cases ORDER BY created_at DESC"
            )

    return CaseListResponse(
        count=len(rows),
        cases=[CaseSummary(**dict(r)) for r in rows],
    )


@app.get("/api/cases/{case_id}", response_model=CaseDetail)
async def get_case(case_id: str):
    """Get case detail with all interactions."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        case = await conn.fetchrow(
            "SELECT * FROM cases WHERE case_id = $1", case_id
        )
        if not case:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

        interactions = await conn.fetch(
            "SELECT interaction_id, case_id, agent_name, message, created_at "
            "FROM interactions WHERE case_id = $1 ORDER BY created_at",
            case_id,
        )

    return CaseDetail(
        case_id=case["case_id"],
        status=case["status"],
        priority=case["priority"],
        summary=case["summary"],
        created_at=case["created_at"],
        updated_at=case["updated_at"],
        coordinates=json.loads(case["coordinates"]) if case["coordinates"] else None,
        interactions=[
            InteractionOut(
                interaction_id=i["interaction_id"],
                case_id=i["case_id"],
                agent_name=i["agent_name"],
                message=i["message"],
                timestamp=i["created_at"],
            )
            for i in interactions
        ],
    )


# ── SSE Stream (live updates for dashboard) ──────────────────

@app.get("/api/stream")
async def stream():
    """Server-Sent Events stream for live case/interaction updates."""
    queue: asyncio.Queue = asyncio.Queue()
    _sse_subscribers.append(queue)

    async def event_generator():
        try:
            # Send initial ping
            yield {"event": "connected", "data": json.dumps({"status": "ok"})}
            while True:
                msg = await queue.get()
                yield msg
        except asyncio.CancelledError:
            pass
        finally:
            _sse_subscribers.remove(queue)

    return EventSourceResponse(event_generator())


# ── Poll for new interactions (simple approach) ──────────────
# Polls DB every 2 seconds for new interactions and broadcasts via SSE.
# In production, use LISTEN/NOTIFY or a message queue.

_last_interaction_id: int = 0


async def _poll_new_interactions():
    """Background task that polls for new interactions and broadcasts via SSE."""
    global _last_interaction_id
    try:
        # Initialize with current max ID
        pool = await get_pool()
        async with pool.acquire() as conn:
            max_id = await conn.fetchval(
                "SELECT COALESCE(MAX(interaction_id), 0) FROM interactions"
            )
            _last_interaction_id = max_id

        while True:
            await asyncio.sleep(2)
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT i.interaction_id, i.case_id, i.agent_name, "
                        "i.message, i.created_at, c.status, c.priority "
                        "FROM interactions i JOIN cases c ON i.case_id = c.case_id "
                        "WHERE i.interaction_id > $1 ORDER BY i.interaction_id",
                        _last_interaction_id,
                    )
                    for row in rows:
                        _broadcast_sse("new_interaction", {
                            "interaction_id": row["interaction_id"],
                            "case_id": row["case_id"],
                            "agent_name": row["agent_name"],
                            "message": row["message"],
                            "timestamp": row["created_at"].isoformat(),
                            "case_status": row["status"],
                            "case_priority": row["priority"],
                        })
                        _last_interaction_id = row["interaction_id"]

                    # Also check for new cases
                    new_cases = await conn.fetch(
                        "SELECT case_id, status, priority, summary, created_at "
                        "FROM cases WHERE created_at > NOW() - INTERVAL '3 seconds' "
                        "ORDER BY created_at"
                    )
                    for c in new_cases:
                        _broadcast_sse("new_case", {
                            "case_id": c["case_id"],
                            "status": c["status"],
                            "priority": c["priority"],
                            "summary": c["summary"],
                            "created_at": c["created_at"].isoformat(),
                        })
            except Exception as e:
                logger.warning("SSE poll error: %s", e)

    except asyncio.CancelledError:
        pass


# ── Operator Messages ────────────────────────────────────────
# Placeholder — will integrate MAF workflow in Phase 3

@app.post("/api/messages", response_model=MessageResponse)
async def handle_message(body: OperatorMessage):
    """Process operator text message through the agent workflow.

    Currently a placeholder — returns a stub response.
    MAF workflow integration will be added in Phase 3/7.
    """
    # TODO: Phase 3/7 — invoke MAF workflow here
    # response_text = await run_workflow(body.text)
    return MessageResponse(
        response=f"[BMS API placeholder] Received: {body.text}"
    )


# ── Entry point ──────────────────────────────────────────────

def main():
    import uvicorn
    uvicorn.run(
        "bms_api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
