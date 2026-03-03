"""
BMS API — Pydantic Schemas
===========================
Request/response models for the REST API.
"""

from datetime import datetime

from pydantic import BaseModel


# ── Cases ─────────────────────────────────────────────────────

class CaseSummary(BaseModel):
    case_id: str
    status: str
    priority: str
    summary: str
    created_at: datetime
    updated_at: datetime


class InteractionOut(BaseModel):
    interaction_id: int
    case_id: str
    agent_name: str
    message: str
    timestamp: datetime


class CaseDetail(CaseSummary):
    coordinates: dict | None = None
    interactions: list[InteractionOut] = []


class CaseListResponse(BaseModel):
    count: int
    cases: list[CaseSummary]


# ── Messages ──────────────────────────────────────────────────

class OperatorMessage(BaseModel):
    text: str


class MessageResponse(BaseModel):
    response: str


# ── SSE Events ────────────────────────────────────────────────

class SSEEvent(BaseModel):
    event: str
    data: dict
