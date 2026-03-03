"""
Level 3 — Operations Workflow (Top-level HandoffBuilder)
=========================================================
The outermost workflow — this is the entry point operators interact with.

Routes between:
  - Orchestrator (start agent — receives walkie-talkie comms from operators)
  - CaseManager (incident case CRUD)
  - FieldSpecialist (facade → L2 HandoffBuilder → L1 ConcurrentBuilder)

This is the only workflow that exposes HITL (Human-in-the-loop) via
``HandoffAgentUserRequest`` — the operator is the human.
"""

from __future__ import annotations

from typing import Any

from agent_framework.ollama import OllamaChatClient
from agent_framework.orchestrations import HandoffBuilder

from src.agents.case_manager import create_case_manager
from src.agents.orchestrator import create_orchestrator
from src.config import MAX_CONVERSATION_TURNS
from src.workflows.field import create_field_specialist_facade


def build_operations_workflow(client: OllamaChatClient) -> Any:
    """Build the top-level BMS Operations workflow.

    Returns the built workflow object — callers use ``.run()`` with
    streaming and process ``HandoffAgentUserRequest`` events for HITL.
    """
    orchestrator = create_orchestrator(client)
    case_manager = create_case_manager(client)
    field_specialist = create_field_specialist_facade(client)

    workflow = (
        HandoffBuilder(
            name="bms_operations",
            participants=[orchestrator, case_manager, field_specialist],
            termination_condition=lambda conv: len(conv) >= MAX_CONVERSATION_TURNS,
        )
        .with_start_agent(orchestrator)
        .add_handoff(orchestrator, [case_manager, field_specialist])
        .add_handoff(case_manager, [orchestrator])
        .add_handoff(field_specialist, [orchestrator])
        .build()
    )

    return workflow
