"""
BMS API — MAF Workflow Integration
====================================
Bridges the FastAPI /api/messages endpoint to the MAF 3-level
nested workflow (Orchestrator → CaseManager / FieldSpecialist).

The workflow is built once and reused across requests.
HITL requests at L3 are auto-responded to continue the flow.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agent_framework import AgentResponse
from agent_framework.orchestrations import HandoffAgentUserRequest

logger = logging.getLogger(__name__)

# ── Workflow singleton ────────────────────────────────────────

_workflow: Any = None
_workflow_lock = asyncio.Lock()


async def _get_workflow() -> Any:
    """Get or build the MAF workflow (singleton)."""
    global _workflow
    if _workflow is None:
        async with _workflow_lock:
            if _workflow is None:
                # Import here to avoid circular imports and to
                # let telemetry configure first
                from src.client import get_client
                from src.workflows.operations import build_operations_workflow

                logger.info("Building MAF 3-level workflow...")
                client = get_client()
                _workflow = build_operations_workflow(client)
                logger.info("MAF workflow ready")
    return _workflow


# ── Run workflow for a single message ─────────────────────────

async def run_agent_workflow(operator_text: str) -> str:
    """Send operator text through the MAF workflow and return agent response.

    Handles the HITL loop automatically:
    - First message starts the workflow
    - If the workflow pauses for HITL, we auto-respond with the
      operator text (single-turn for API mode)
    - Collects all agent text outputs and returns them joined

    Returns the agent's response text.
    """
    workflow = await _get_workflow()

    agent_texts: list[str] = []
    seen: set[str] = set()

    def _collect_texts(events: list[Any]) -> list[Any]:
        """Extract agent text and HITL requests from events."""
        pending = []
        for event in events:
            if event.type == "output":
                data = event.data
                if isinstance(data, AgentResponse):
                    for message in data.messages:
                        if not message.text:
                            continue
                        key = f"{message.author_name}:{message.text[:100]}"
                        if key in seen:
                            continue
                        seen.add(key)
                        agent_texts.append(message.text)

            elif event.type == "request_info" and isinstance(
                event.data, HandoffAgentUserRequest
            ):
                # Collect the agent message that comes with the HITL request
                if hasattr(event.data, "agent_response") and event.data.agent_response:
                    for message in event.data.agent_response.messages:
                        if message.text:
                            key = f"{message.author_name}:{message.text[:100]}"
                            if key in seen:
                                continue
                            seen.add(key)
                            agent_texts.append(message.text)
                pending.append(event)
        return pending

    try:
        # Initial run
        result = workflow.run(operator_text, stream=True)
        events = [event async for event in result]
        pending = _collect_texts(events)

        # Auto-respond to HITL requests (max 3 rounds)
        rounds = 0
        while pending and rounds < 3:
            rounds += 1
            logger.debug("HITL round %d: %d pending requests", rounds, len(pending))

            # Terminate all pending requests (single-turn API mode)
            responses = {
                req.request_id: HandoffAgentUserRequest.terminate()
                for req in pending
            }
            result = await workflow.run(responses=responses)

            if hasattr(result, "__aiter__"):
                events = [event async for event in result]
            elif isinstance(result, list):
                events = result
            else:
                events = []

            pending = _collect_texts(events)

    except Exception as e:
        logger.error("Workflow error: %s", e, exc_info=True)
        return f"Error processing request: {e}"

    if not agent_texts:
        return "No response from agents."

    # Return the last substantive agent message
    return agent_texts[-1]
