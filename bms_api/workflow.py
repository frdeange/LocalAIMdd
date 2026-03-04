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
        print(f"[WORKFLOW] Processing {len(events)} events", flush=True)
        for event in events:
            print(f"[WORKFLOW] Event type={event.type} data_type={type(event.data).__name__}", flush=True)
            if event.type == "output":
                data = event.data
                if isinstance(data, AgentResponse):
                    for message in data.messages:
                        print(f"[WORKFLOW] Message author={message.author_name} text={message.text[:100] if message.text else 'None'}", flush=True)
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
        # Run workflow in NON-streaming mode — lets HandoffBuilder complete
        # the full chain (Orchestrator → FieldSpecialist → Recon → MCP tools)
        # before pausing for HITL
        print(f"[WORKFLOW] Starting workflow with: {operator_text[:100]}", flush=True)
        result = await workflow.run(operator_text)
        
        # result is the final AgentResponse or a list of events
        print(f"[WORKFLOW] Result type: {type(result).__name__}", flush=True)
        
        # WorkflowRunResult is a list with get_outputs() and get_request_info_events()
        outputs = result.get_outputs() if hasattr(result, 'get_outputs') else []
        requests = result.get_request_info_events() if hasattr(result, 'get_request_info_events') else []
        
        print(f"[WORKFLOW] Outputs: {len(outputs)}, HITL requests: {len(requests)}", flush=True)
        
        # Extract text from outputs
        for output in outputs:
            data = output.data if hasattr(output, 'data') else output
            print(f"[WORKFLOW] Output type: {type(data).__name__}", flush=True)
            
            if isinstance(data, AgentResponse):
                for message in data.messages:
                    if hasattr(message, 'text') and message.text:
                        print(f"[WORKFLOW] Agent [{getattr(message, 'author_name', '?')}]: {message.text[:150]}", flush=True)
                        if not _is_noise(message.text):
                            key = f"{getattr(message, 'author_name', '')}:{message.text[:100]}"
                            if key not in seen:
                                seen.add(key)
                                agent_texts.append(message.text)
            elif isinstance(data, list):
                # Conversation snapshot
                for item in data:
                    if hasattr(item, 'text') and item.text:
                        print(f"[WORKFLOW] Conv [{getattr(item, 'author_name', '?')}]: {item.text[:150]}", flush=True)
                        if not _is_noise(item.text):
                            key = f"{getattr(item, 'author_name', '')}:{item.text[:100]}"
                            if key not in seen:
                                seen.add(key)
                                agent_texts.append(item.text)
            else:
                print(f"[WORKFLOW] Unknown output: {str(data)[:200]}", flush=True)
        
        # Also check HITL requests for agent messages
        for req_event in requests:
            req = req_event.data if hasattr(req_event, 'data') else req_event
            if hasattr(req, 'agent_response') and req.agent_response:
                for message in req.agent_response.messages:
                    if hasattr(message, 'text') and message.text:
                        print(f"[WORKFLOW] HITL agent [{getattr(message, 'author_name', '?')}]: {message.text[:150]}", flush=True)
                        if not _is_noise(message.text):
                            key = f"{getattr(message, 'author_name', '')}:{message.text[:100]}"
                            if key not in seen:
                                seen.add(key)
                                agent_texts.append(message.text)

    except Exception as e:
        print(f"[WORKFLOW] Error: {e}", flush=True)
        logger.error("Workflow error: %s", e, exc_info=True)
        return f"Error procesando la solicitud: {e}"

    if not agent_texts:
        print("[WORKFLOW] No agent texts collected!", flush=True)
        return "No se recibió respuesta de los agentes. Intente de nuevo."

    # Return the last substantive agent message
    print(f"[WORKFLOW] Returning response ({len(agent_texts)} texts, using last)", flush=True)
    return agent_texts[-1]
