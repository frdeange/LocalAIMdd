"""
Pydantic Schemas
================
Request/response models for the API endpoints.
Separated from ORM models to maintain clean boundaries.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# ── Conversation Schemas ──────────────────────────────────────

class ConversationCreate(BaseModel):
    """Request body for creating a new conversation."""
    title: str = Field(default="New Conversation", max_length=255)


class MessageResponse(BaseModel):
    """A single message in a conversation."""
    id: str
    role: str
    author_name: str | None = None
    content: str
    step_number: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    """Full conversation with messages."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = []

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    """Conversation list item (without messages)."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


# ── Message Schemas ───────────────────────────────────────────

class MessageCreate(BaseModel):
    """Request body for sending a new message (triggers workflow)."""
    content: str = Field(..., min_length=1, max_length=4096)


# ── SSE Event Schemas ─────────────────────────────────────────

class SSEEvent(BaseModel):
    """Base SSE event data."""
    type: str


class WorkflowStartedEvent(SSEEvent):
    """Emitted when the workflow begins."""
    type: str = "workflow_started"
    workflow: str = "travel_planner"


class AgentStartedEvent(SSEEvent):
    """Emitted when an agent begins processing."""
    type: str = "agent_started"
    agent: str
    step: int


class AgentCompletedEvent(SSEEvent):
    """Emitted when an agent completes processing."""
    type: str = "agent_completed"
    agent: str
    step: int
    output: str


class WorkflowCompletedEvent(SSEEvent):
    """Emitted when the entire workflow completes."""
    type: str = "workflow_completed"
    final_output: str


class WorkflowErrorEvent(SSEEvent):
    """Emitted when an error occurs."""
    type: str = "error"
    message: str
