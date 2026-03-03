"""
MCP BMS Service — Case Management (PostgreSQL)
===============================================
FastMCP server that provides CRUD operations for BMS cases and
interactions, backed by a real PostgreSQL database.

Unlike Camera and Weather (simulated), this service persists real data.

Run:  python -m mcp_services.bms_server
Default: streamable-http on port 8093

Environment variables:
    DATABASE_URL      PostgreSQL connection string
    MCP_BMS_PORT      Server port (default: 8093)
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Annotated

from mcp_services.telemetry import configure_telemetry

configure_telemetry("mcp-bms")

import asyncpg
from fastmcp import FastMCP

mcp = FastMCP(
    name="BMS Case Management Service",
    instructions=(
        "Manages BMS incident cases and interaction logs. "
        "Provides tools to create, update, and query cases, "
        "and to log agent interactions against cases."
    ),
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bms_ops:BmsOps2026@localhost:5432/bms_ops",
)

# ── Connection pool (lazy init) ──────────────────────────────
_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


# ── Case ID generation ───────────────────────────────────────
async def _next_case_id(conn: asyncpg.Connection) -> str:
    """Generate next sequential case ID: BMS-YYYY-NNN."""
    year = datetime.now(timezone.utc).year
    prefix = f"BMS-{year}-"
    row = await conn.fetchrow(
        "SELECT case_id FROM cases WHERE case_id LIKE $1 ORDER BY case_id DESC LIMIT 1",
        f"{prefix}%",
    )
    if row:
        last_num = int(row["case_id"].split("-")[-1])
        return f"{prefix}{last_num + 1:03d}"
    return f"{prefix}001"


# ── MCP Tools ────────────────────────────────────────────────


@mcp.tool()
async def create_case(
    summary: Annotated[str, "Brief description of the incident"],
    priority: Annotated[str, "Priority level: LOW, MEDIUM, HIGH, or CRITICAL"] = "MEDIUM",
    coordinates: Annotated[str, "Coordinates as 'lat,lon' or descriptive text"] = "",
) -> str:
    """Create a new BMS incident case. Returns the assigned case ID."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        case_id = await _next_case_id(conn)
        coords_json = None
        if coordinates:
            # Try to parse "lat,lon" format
            try:
                parts = [float(x.strip()) for x in coordinates.split(",")]
                if len(parts) == 2:
                    coords_json = json.dumps({"latitude": parts[0], "longitude": parts[1]})
            except ValueError:
                coords_json = json.dumps({"raw": coordinates})

        await conn.execute(
            """INSERT INTO cases (case_id, status, priority, summary, coordinates)
               VALUES ($1, 'OPEN', $2, $3, $4::jsonb)""",
            case_id,
            priority.upper(),
            summary,
            coords_json,
        )

    return json.dumps({"case_id": case_id, "status": "OPEN", "priority": priority.upper()})


@mcp.tool()
async def update_case(
    case_id: Annotated[str, "Case ID to update (e.g. BMS-2026-001)"],
    status: Annotated[str, "New status: OPEN, IN_PROGRESS, or CLOSED"] = "",
    priority: Annotated[str, "New priority: LOW, MEDIUM, HIGH, or CRITICAL"] = "",
) -> str:
    """Update the status and/or priority of an existing BMS case."""
    pool = await _get_pool()
    updates = []
    params = []
    idx = 1

    if status:
        idx += 1
        updates.append(f"status = ${idx}")
        params.append(status.upper())
    if priority:
        idx += 1
        updates.append(f"priority = ${idx}")
        params.append(priority.upper())

    if not updates:
        return json.dumps({"error": "No fields to update"})

    updates.append("updated_at = NOW()")
    sql = f"UPDATE cases SET {', '.join(updates)} WHERE case_id = $1"
    params.insert(0, case_id)

    async with pool.acquire() as conn:
        result = await conn.execute(sql, *params)

    if result == "UPDATE 0":
        return json.dumps({"error": f"Case {case_id} not found"})

    updated = {}
    if status:
        updated["status"] = status.upper()
    if priority:
        updated["priority"] = priority.upper()

    return json.dumps({"case_id": case_id, "updated": updated})


@mcp.tool()
async def add_interaction(
    case_id: Annotated[str, "Case ID to add interaction to"],
    agent_name: Annotated[str, "Name of the agent logging this interaction"],
    message: Annotated[str, "Interaction message content"],
) -> str:
    """Log an agent interaction against a BMS case."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        # Verify case exists
        exists = await conn.fetchval("SELECT 1 FROM cases WHERE case_id = $1", case_id)
        if not exists:
            return json.dumps({"error": f"Case {case_id} not found"})

        row = await conn.fetchrow(
            """INSERT INTO interactions (case_id, agent_name, message)
               VALUES ($1, $2, $3) RETURNING interaction_id, created_at""",
            case_id,
            agent_name,
            message,
        )

        # Update case timestamp
        await conn.execute("UPDATE cases SET updated_at = NOW() WHERE case_id = $1", case_id)

    return json.dumps({
        "interaction_id": row["interaction_id"],
        "case_id": case_id,
        "timestamp": row["created_at"].isoformat(),
    })


@mcp.tool()
async def get_case(
    case_id: Annotated[str, "Case ID to retrieve"],
) -> str:
    """Get full details of a BMS case including all interactions."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        case = await conn.fetchrow("SELECT * FROM cases WHERE case_id = $1", case_id)
        if not case:
            return json.dumps({"error": f"Case {case_id} not found"})

        interactions = await conn.fetch(
            "SELECT * FROM interactions WHERE case_id = $1 ORDER BY created_at",
            case_id,
        )

    return json.dumps({
        "case_id": case["case_id"],
        "created_at": case["created_at"].isoformat(),
        "updated_at": case["updated_at"].isoformat(),
        "status": case["status"],
        "priority": case["priority"],
        "summary": case["summary"],
        "coordinates": json.loads(case["coordinates"]) if case["coordinates"] else None,
        "interactions": [
            {
                "interaction_id": i["interaction_id"],
                "agent_name": i["agent_name"],
                "message": i["message"],
                "timestamp": i["created_at"].isoformat(),
            }
            for i in interactions
        ],
    })


@mcp.tool()
async def list_cases(
    status: Annotated[str, "Filter by status (OPEN, IN_PROGRESS, CLOSED) or empty for all"] = "",
) -> str:
    """List all BMS cases, optionally filtered by status."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT case_id, status, priority, summary, created_at FROM cases WHERE status = $1 ORDER BY created_at DESC",
                status.upper(),
            )
        else:
            rows = await conn.fetch(
                "SELECT case_id, status, priority, summary, created_at FROM cases ORDER BY created_at DESC"
            )

    return json.dumps({
        "count": len(rows),
        "cases": [
            {
                "case_id": r["case_id"],
                "status": r["status"],
                "priority": r["priority"],
                "summary": r["summary"][:100],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    })


if __name__ == "__main__":
    port = int(os.getenv("MCP_BMS_PORT", "8093"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
