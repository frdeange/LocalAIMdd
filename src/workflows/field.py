"""
Level 2 — Field Operations Workflow (HandoffBuilder)
=====================================================
Routes between:
  - FieldCoordinator (start agent — decides routing)
  - ReconAgent (facade → ConcurrentBuilder of Camera + Meteo)
  - VehicleExpert

Also provides ``create_field_specialist_facade()`` which wraps this
entire HandoffBuilder in a real Agent, enabling it to participate in the
Level 3 workflow via the Agent-as-facade pattern.
"""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import Agent, AgentResponse
from agent_framework.ollama import OllamaChatClient
from agent_framework.orchestrations import (
    HandoffAgentUserRequest,
    HandoffBuilder,
)

from src.agents.field_coordinator import create_field_coordinator
from src.agents.vehicle import create_vehicle_agent
from src.workflows.recon import create_recon_facade


# ── Workflow factory ──────────────────────────────────────────

def build_field_workflow(client: OllamaChatClient) -> Any:
    """Build the Level 2 HandoffBuilder (FieldCoord → Recon | Vehicle).

    Returns the built workflow object.
    """
    coordinator = create_field_coordinator(client)
    recon_agent = create_recon_facade(client)
    vehicle_expert = create_vehicle_agent(client)

    workflow = (
        HandoffBuilder(
            name="field_operations",
            participants=[coordinator, recon_agent, vehicle_expert],
            termination_condition=lambda conv: len(conv) >= 20,
        )
        .with_start_agent(coordinator)
        .add_handoff(coordinator, [recon_agent, vehicle_expert])
        .add_handoff(recon_agent, [coordinator])
        .add_handoff(vehicle_expert, [coordinator])
        .build()
    )

    return workflow


# ── Helpers ───────────────────────────────────────────────────

def _collect_outputs(events: list[Any]) -> tuple[list[str], list[Any]]:
    """Extract text outputs and pending HITL requests from workflow events."""
    parts: list[str] = []
    requests: list[Any] = []

    for event in events:
        if event.type == "output":
            data = event.data
            if isinstance(data, AgentResponse):
                for msg in data.messages:
                    if msg.text:
                        speaker = msg.author_name or msg.role
                        parts.append(f"[{speaker}]: {msg.text}")
            elif isinstance(data, list):
                for msg in data:
                    if hasattr(msg, "text") and msg.text:
                        speaker = getattr(msg, "author_name", None) or getattr(msg, "role", "agent")
                        parts.append(f"[{speaker}]: {msg.text}")
        elif event.type == "request_info" and isinstance(event.data, HandoffAgentUserRequest):
            # Inner workflow paused waiting for "user" input — we'll auto-respond
            if hasattr(event.data, "agent_response") and event.data.agent_response:
                for msg in event.data.agent_response.messages:
                    if msg.text:
                        speaker = msg.author_name or msg.role
                        parts.append(f"[{speaker}]: {msg.text}")
            requests.append(event)

    return parts, requests


# ── Agent-as-facade ───────────────────────────────────────────
_field_workflow: Any = None

# Auto-responses injected when the inner HandoffBuilder asks for "user" input.
# This lets the L2 workflow run autonomously without a real human.
_AUTO_RESPONSES = [
    "Proceed with the assessment. Use all available specialists and compile a full report.",
    "Continue. Compile all findings from specialists into a final summary.",
    "Wrap up and provide the complete report.",
]


async def run_field_operations(
    task: Annotated[str, "Full description of the field task to execute — include coordinates, vehicle descriptions, or any relevant details"],
) -> str:
    """Execute a complete field operation: may include reconnaissance (camera + weather) and/or vehicle identification."""
    global _field_workflow

    if _field_workflow is None:
        return "ERROR: Field operations workflow not initialised."

    # Phase 1: Initial run — stream events from the inner HandoffBuilder
    result = _field_workflow.run(task, stream=True)
    events = [event async for event in result]
    report_parts, pending = _collect_outputs(events)

    # Phase 2: Auto-respond to inner HITL requests (max 3 rounds)
    round_idx = 0
    while pending and round_idx < len(_AUTO_RESPONSES):
        auto_msg = _AUTO_RESPONSES[round_idx]
        round_idx += 1

        responses = {
            req.request_id: HandoffAgentUserRequest.create_response(auto_msg)
            for req in pending
        }
        events = await _field_workflow.run(responses=responses)
        new_parts, pending = _collect_outputs(events)
        report_parts.extend(new_parts)

    # Phase 3: Terminate any remaining requests
    if pending:
        responses = {
            req.request_id: HandoffAgentUserRequest.terminate()
            for req in pending
        }
        events = await _field_workflow.run(responses=responses)
        new_parts, _ = _collect_outputs(events)
        report_parts.extend(new_parts)

    return "\n\n".join(report_parts) if report_parts else (
        "Field operations completed but no reports were generated."
    )


def create_field_specialist_facade(client: OllamaChatClient) -> Agent:
    """Create the FieldSpecialist facade — real Agent wrapping the L2 workflow.

    Also builds and stores the inner HandoffBuilder workflow (which in turn
    builds the L1 ConcurrentBuilder via ReconAgent facade).
    """
    global _field_workflow
    _field_workflow = build_field_workflow(client)

    field_specialist = client.as_agent(
        name="FieldSpecialist",
        instructions=(
            "You are a field specialist coordinator. You have TWO tools:\n\n"
            "1. ``run_field_operations`` — runs recon (camera + weather) and "
            "vehicle ID. Call this with the full task description.\n"
            "2. ``transfer_to_Orchestrator`` — hands control back.\n\n"
            "STRICT WORKFLOW (follow every time):\n"
            "Step 1: Call ``run_field_operations`` with ALL details.\n"
            "Step 2: Summarise the results in 3-5 lines.\n"
            "Step 3: IMMEDIATELY call ``transfer_to_Orchestrator``.\n\n"
            "CRITICAL RULES:\n"
            "- After reporting results, ALWAYS transfer back. No exceptions.\n"
            "- If the user asks something unrelated to field ops (e.g. "
            "'create case', 'case status'), call ``transfer_to_Orchestrator`` "
            "immediately WITHOUT calling run_field_operations.\n"
            "- NEVER answer more than ONE round without transferring back.\n"
            "- NEVER fabricate data."
        ),
        tools=[run_field_operations],
    )
    return field_specialist
