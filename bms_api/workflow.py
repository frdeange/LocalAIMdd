"""
BMS API — MAF Workflow Integration
====================================
Bridges the FastAPI /api/messages endpoint to the MAF agents.

Strategy: Instead of using the L3 HandoffBuilder (which requires
tool-calling for routing and fails with qwen2.5:7b generating text
instead of tool calls), we call the agents directly:

- Field operations (recon, weather, vehicle) → run_field_operations()
  This function handles the L2 HandoffBuilder + L1 ConcurrentBuilder
  internally with auto-HITL responses (proven to work).

- Case management → CaseManager agent directly

The routing decision (which agent to call) is done with simple keyword
matching on the operator text, bypassing the unreliable LLM routing.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Client (reusable) ────────────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is None:
        from src.client import get_client
        _client = get_client()
    return _client


# ── Field operations (L2 + L1 workflows) ─────────────────────

_field_initialized = False


def _ensure_field_initialized():
    """Initialize the field operations workflow (L2 + L1)."""
    global _field_initialized
    if not _field_initialized:
        from src.workflows.field import create_field_specialist_facade
        create_field_specialist_facade(_get_client())
        _field_initialized = True
        print("[WF] Field operations initialized (L2+L1)", flush=True)


# ── Case management agent ────────────────────────────────────

_case_manager = None


def _get_case_manager():
    global _case_manager
    if _case_manager is None:
        from src.agents.case_manager import create_case_manager
        _case_manager = create_case_manager(_get_client())
        print("[WF] CaseManager initialized", flush=True)
    return _case_manager


# ── Simple intent routing ────────────────────────────────────

CASE_KEYWORDS = re.compile(
    r'caso|case|crear caso|create case|cerrar|close|prioridad|priority|'
    r'estado del caso|case status|incidente|incident',
    re.IGNORECASE,
)


def _route_intent(text: str) -> str:
    """Route: 'case' for case management, 'field' for everything else."""
    if CASE_KEYWORDS.search(text):
        return "case"
    return "field"


# ── Run workflow ─────────────────────────────────────────────

async def run_agent_workflow(operator_text: str) -> str:
    """Send operator text through the appropriate agent(s)."""
    intent = _route_intent(operator_text)
    print(f"[WF] Intent: {intent} | Text: {operator_text[:100]}", flush=True)

    try:
        if intent == "case":
            return await _handle_case(operator_text)
        else:
            return await _handle_field(operator_text)
    except Exception as e:
        print(f"[WF] Error: {e}", flush=True)
        logger.error("Workflow error: %s", e, exc_info=True)
        return f"Error procesando la solicitud: {e}"


async def _handle_field(operator_text: str) -> str:
    """Run field operations (recon + weather + vehicle ID)."""
    _ensure_field_initialized()

    from src.workflows.field import run_field_operations
    print("[WF] Calling run_field_operations...", flush=True)

    result = await run_field_operations(operator_text)
    print(f"[WF] Field result ({len(result)} chars): {result[:200]}", flush=True)

    if not result or "ERROR" in result:
        return "No se pudo completar la operacion de campo. Intente de nuevo."

    # Clean up — remove speaker tags like [CameraAgent]:
    lines = result.split("\n")
    clean_lines = []
    for line in lines:
        cleaned = re.sub(r'^\[[\w]+\]:\s*', '', line.strip())
        if cleaned:
            clean_lines.append(cleaned)

    return "\n".join(clean_lines) if clean_lines else result


async def _handle_case(operator_text: str) -> str:
    """Run case management via CaseManager agent."""
    agent = _get_case_manager()
    print("[WF] Calling CaseManager agent...", flush=True)

    response = await agent.run(operator_text)
    text = response.text if hasattr(response, 'text') and response.text else None

    if not text and hasattr(response, 'messages'):
        for msg in response.messages:
            if hasattr(msg, 'text') and msg.text:
                text = msg.text
                break

    print(f"[WF] Case result: {text[:200] if text else 'No response'}", flush=True)
    return text or "No se recibio respuesta del gestor de casos."
