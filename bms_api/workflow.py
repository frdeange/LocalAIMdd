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

# ── Workflow (built fresh per request) ────────────────────────

_client = None


def _get_client():
    """Get or create the Ollama client (reusable)."""
    global _client
    if _client is None:
        from src.client import get_client
        _client = get_client()
    return _client


def _build_workflow():
    """Build a fresh MAF workflow for each request.
    
    HandoffBuilder workflows are STATEFUL — they cannot be reused
    across requests. Each operator message needs a fresh workflow.
    """
    from src.workflows.operations import build_operations_workflow
    client = _get_client()
    return build_operations_workflow(client)


# ── Run workflow for a single message ─────────────────────────

async def run_agent_workflow(operator_text: str) -> str:
    """Send operator text through the MAF workflow and return agent response.

    Handles the HITL loop automatically:
    - First message starts the workflow
    - If the workflow pauses for HITL (agent waiting for operator),
      we auto-respond to let the agents continue working
    - Collects all agent text outputs, filters out handoff noise
    - Returns the last substantive agent response

    Returns the agent's response text.
    """
    workflow = _build_workflow()
    logger.info("Fresh workflow built for operator message")

    agent_texts: list[str] = []
    seen: set[str] = set()

    # Patterns to filter out (handoff function names, not real responses)
    NOISE_PATTERNS = [
        "transfer_to_",
        "_to_",           # catches garbled versions like "brtc_to_"
        "handoff",
        "HANDOFF",
        "FieldSpecialist",
        "CaseManager",
        "ReconAgent",
        "VehicleExpert",
        "Coordinator",
    ]

    def _is_noise(text: str) -> bool:
        """Check if text is a handoff routing message, not a real response."""
        stripped = text.strip()
        # Too short to be a real response
        if len(stripped) < 20:
            return True
        # Contains handoff/routing patterns
        if any(p in stripped for p in NOISE_PATTERNS):
            # But only if it's a SHORT message (real reports can mention agent names)
            if len(stripped) < 100:
                return True
        return False

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
                        if _is_noise(message.text):
                            logger.info("Filtered noise: %s", message.text[:80])
                        else:
                            logger.info("Agent text [%s]: %s", message.author_name, message.text[:120])
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
                            if _is_noise(message.text):
                                logger.info("Filtered HITL noise: %s", message.text[:80])
                            else:
                                logger.info("HITL agent text [%s]: %s", message.author_name, message.text[:120])
                                agent_texts.append(message.text)
                logger.info("HITL request received — will auto-continue")
                pending.append(event)
        return pending

    try:
        # Initial run
        result = workflow.run(operator_text, stream=True)
        events = [event async for event in result]
        pending = _collect_texts(events)

        # Auto-respond to HITL requests (max 5 rounds to let agents complete)
        rounds = 0
        while pending and rounds < 5:
            rounds += 1
            logger.info("HITL round %d: %d pending requests — auto-continuing", rounds, len(pending))

            # Send "continue" response so agents keep working
            responses = {
                req.request_id: HandoffAgentUserRequest.create_response(
                    "Recibido. Continúe con el análisis y proporcione su informe completo."
                )
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
        logger.warning("No agent texts collected after %d HITL rounds", rounds)
        return "No se recibió respuesta de los agentes. Intente de nuevo."

    # Return the last substantive agent message
    logger.info("Returning agent response (%d texts collected, using last)", len(agent_texts))
    return agent_texts[-1]
