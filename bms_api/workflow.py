"""
BMS API — MAF Workflow Integration
====================================
Bridges the FastAPI /api/messages endpoint to the MAF 3-level
nested workflow (Orchestrator → CaseManager / FieldSpecialist).

Replicates the exact event-processing pattern from src/runner.py
which is proven to work.
"""

from __future__ import annotations

import logging
from typing import Any

from agent_framework import AgentResponse
from agent_framework.orchestrations import HandoffAgentUserRequest

logger = logging.getLogger(__name__)

# ── Client (reusable) ────────────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is None:
        from src.client import get_client
        _client = get_client()
    return _client


def _build_workflow():
    """Fresh workflow per request (HandoffBuilder is stateful)."""
    from src.workflows.operations import build_operations_workflow
    return build_operations_workflow(_get_client())


# ── Event processing (mirrors runner.py process_events) ──────

def _process_events(events: list[Any]) -> tuple[list[str], list[Any]]:
    """Extract agent texts and pending HITL requests from workflow events.
    
    Returns (agent_texts, pending_hitl_events).
    pending_hitl_events are the RAW WorkflowEvent objects (have .request_id).
    """
    texts: list[str] = []
    pending: list[Any] = []
    seen: set[str] = set()

    for event in events:
        if event.type == "output":
            data = event.data
            if isinstance(data, AgentResponse):
                for message in data.messages:
                    if not message.text:
                        continue
                    key = f"{message.author_name}:{message.text[:80]}"
                    if key in seen:
                        continue
                    seen.add(key)
                    texts.append(message.text)
                    print(f"[WF] Agent [{message.author_name}]: {message.text[:120]}", flush=True)

        elif event.type == "request_info" and isinstance(event.data, HandoffAgentUserRequest):
            # Extract text from the agent response that accompanies the HITL request
            if event.data.agent_response:
                for message in event.data.agent_response.messages:
                    if message.text:
                        key = f"{message.author_name}:{message.text[:80]}"
                        if key in seen:
                            continue
                        seen.add(key)
                        texts.append(message.text)
                        print(f"[WF] HITL [{message.author_name}]: {message.text[:120]}", flush=True)
            # Keep the RAW EVENT (has .request_id)
            pending.append(event)
            print(f"[WF] HITL request pending (id={event.request_id})", flush=True)

    return texts, pending


# ── Run workflow ─────────────────────────────────────────────

async def run_agent_workflow(operator_text: str) -> str:
    """Send operator text through the MAF workflow and return agent response.
    
    Pattern copied from runner.py run_demo():
    1. workflow.run(text, stream=True) → collect events
    2. Process events → get texts + HITL requests
    3. Auto-respond to HITL with operator text → continue workflow
    4. Repeat until no more HITL requests
    5. Return last agent text
    """
    workflow = _build_workflow()
    print(f"[WF] Starting: {operator_text[:100]}", flush=True)

    all_texts: list[str] = []

    try:
        # Step 1: Initial run (streaming, like runner.py)
        result = workflow.run(operator_text, stream=True)
        events = [event async for event in result]
        print(f"[WF] Initial: {len(events)} events", flush=True)

        texts, pending = _process_events(events)
        all_texts.extend(texts)

        # Step 2: Auto-respond to HITL requests (max 5 rounds)
        round_num = 0
        while pending and round_num < 5:
            round_num += 1
            print(f"[WF] HITL round {round_num}: {len(pending)} requests", flush=True)

            # Build responses dict: event.request_id → response
            # Use the original operator text as the response (like demo scenario)
            responses = {
                req_event.request_id: HandoffAgentUserRequest.create_response(operator_text)
                for req_event in pending
            }

            # Continue workflow (non-streaming, like runner.py)
            events = await workflow.run(responses=responses)
            print(f"[WF] Round {round_num}: {len(events)} events", flush=True)

            texts, pending = _process_events(events)
            all_texts.extend(texts)

        # Terminate any remaining
        if pending:
            print(f"[WF] Terminating {len(pending)} remaining requests", flush=True)
            responses = {
                req_event.request_id: HandoffAgentUserRequest.terminate()
                for req_event in pending
            }
            events = await workflow.run(responses=responses)
            texts, _ = _process_events(events)
            all_texts.extend(texts)

    except Exception as e:
        print(f"[WF] Error: {e}", flush=True)
        logger.error("Workflow error: %s", e, exc_info=True)
        return f"Error procesando la solicitud: {e}"

    if not all_texts:
        print("[WF] No texts collected!", flush=True)
        return "No se recibió respuesta de los agentes. Intente de nuevo."

    # Filter out noise (handoff function names)
    real_texts = [t for t in all_texts if len(t) > 30 and "_to_" not in t]
    
    if real_texts:
        print(f"[WF] Returning ({len(real_texts)} real texts, using last)", flush=True)
        return real_texts[-1]
    
    # Fallback: return last text even if short
    print(f"[WF] Returning fallback ({len(all_texts)} texts, using last)", flush=True)
    return all_texts[-1]
