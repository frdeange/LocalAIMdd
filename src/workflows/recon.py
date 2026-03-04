"""
Level 1 — Reconnaissance Workflow (ConcurrentBuilder)
======================================================
Fan-out/fan-in: CameraAgent and MeteoAgent run in parallel.

This module also exports ``create_recon_facade()`` which wraps the
workflow in a real ``Agent`` via the Agent-as-facade pattern, making it
compatible with ``HandoffBuilder`` at the next level.
"""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import Agent
from agent_framework.ollama import OllamaChatClient
from agent_framework.orchestrations import ConcurrentBuilder

from src.agents.camera import create_camera_agent
from src.agents.meteo import create_meteo_agent


# ── Workflow factory ──────────────────────────────────────────

def build_recon_workflow(client: OllamaChatClient) -> Any:
    """Build the ConcurrentBuilder that runs Camera + Meteo in parallel.

    Returns the built workflow object (has ``.run(query)``).
    """
    camera = create_camera_agent(client)
    meteo = create_meteo_agent(client)

    workflow = ConcurrentBuilder(
        participants=[camera, meteo],
    ).build()

    return workflow


# ── Agent-as-facade ───────────────────────────────────────────
# A module-level reference to the workflow; set by ``create_recon_facade``.
_recon_workflow: Any = None


async def run_reconnaissance(
    coordinates: Annotated[str, "GPS coordinates for reconnaissance, e.g. '40.41N, 3.70W'"],
    situation: Annotated[str, "Brief description of the situation or target to assess"],
) -> str:
    """Run parallel reconnaissance: camera surveillance + weather assessment for given coordinates."""
    global _recon_workflow

    if _recon_workflow is None:
        return "ERROR: Reconnaissance workflow not initialised."

    query = (
        f"Coordinates: {coordinates}. Situation: {situation}. "
        "Provide your full assessment report."
    )
    result = await _recon_workflow.run(query)
    outputs = result.get_outputs()

    report_parts: list[str] = []
    if outputs:
        for output in outputs:
            if isinstance(output, list):
                for msg in output:
                    if hasattr(msg, "text") and msg.text:
                        speaker = msg.author_name or msg.role
                        report_parts.append(f"[{speaker}]: {msg.text}")
            elif hasattr(output, "text") and output.text:
                report_parts.append(output.text)

    return "\n\n".join(report_parts) if report_parts else (
        "Reconnaissance completed but no data was collected."
    )


def create_recon_facade(client: OllamaChatClient) -> Agent:
    """Create the ReconAgent facade — a real Agent with the recon tool.

    Also builds and stores the inner ConcurrentBuilder workflow.
    """
    global _recon_workflow
    _recon_workflow = build_recon_workflow(client)

    recon_agent = client.as_agent(
        name="ReconAgent",
        instructions=(
            "You are a reconnaissance team coordinator. You have access to "
            "the ``run_reconnaissance`` tool that deploys camera surveillance "
            "and weather assessment teams in parallel.\n\n"
            "IMPORTANT: Always respond in the SAME LANGUAGE as the request. "
            "Do NOT use markdown formatting (no **, #, -). Plain text only.\n\n"
            "When asked to assess a location or perform reconnaissance:\n"
            "1. Extract coordinates and situation from the request.\n"
            "2. Call ``run_reconnaissance`` with those parameters.\n"
            "3. Summarise the combined results in 3-5 concise lines.\n\n"
            "If no coordinates are provided, ask for them. Never invent coordinates."
        ),
        tools=[run_reconnaissance],
    )
    return recon_agent
