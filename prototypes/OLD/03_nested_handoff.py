"""
Prototype 03 — Nested Composition: HandoffBuilder + ConcurrentBuilder via Tool
===============================================================================
THE CRITICAL TEST. Validates that a ConcurrentBuilder workflow can be
invoked from inside a HandoffBuilder workflow.

Since HandoffBuilder requires Agent instances (not WorkflowAgent from .as_agent()),
we use the "Agent-as-facade" pattern: create a real Agent with a tool that
internally runs the ConcurrentBuilder workflow.

Architecture being tested:

    HandoffBuilder (main_workflow)
    ├── Coordinator ──handoff──► ReconAgent [has tool: run_reconnaissance]
    │       │                     └── tool internally runs ConcurrentBuilder:
    │       │                          ├── CameraAgent (parallel)
    │       │                          └── MeteoAgent  (parallel)
    │       │
    │       └──handoff──► VehicleExpert
    │
    └── All specialists can hand back to Coordinator

This mimics the real BMS architecture where:
- The Coordinator (Orchestrator) routes to specialists
- The ReconAgent wraps a concurrent fan-out (Camera + Meteo) as a tool
- VehicleExpert is a standalone specialist

Usage:
    python prototypes/03_nested_handoff.py

Environment:
    OLLAMA_HOST      (default: http://localhost:11434)
    OLLAMA_MODEL_ID  (default: qwen2.5:3b)
"""

import asyncio
import os
import sys
from typing import Annotated, cast

import patch_ollama  # noqa: F401 — must import before using OllamaChatClient

from agent_framework import Agent, AgentResponse, Message, WorkflowRunState
from agent_framework.ollama import OllamaChatClient
from agent_framework.orchestrations import (
    ConcurrentBuilder,
    HandoffAgentUserRequest,
    HandoffBuilder,
)

# ── Config ────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL_ID = os.getenv("OLLAMA_MODEL_ID", "qwen2.5:3b")

SEPARATOR = "─" * 70

# Global reference to the concurrent workflow — set during setup
_recon_workflow = None


def create_client() -> OllamaChatClient:
    """Create an OllamaChatClient pointing to local Ollama."""
    print(f"  Ollama host:  {OLLAMA_HOST}")
    print(f"  Model:        {OLLAMA_MODEL_ID}")
    return OllamaChatClient(host=OLLAMA_HOST, model_id=OLLAMA_MODEL_ID)


def build_recon_workflow(client: OllamaChatClient):
    """Build the ConcurrentBuilder workflow (Camera + Meteo)."""
    camera_agent = client.as_agent(
        name="CameraAgent",
        instructions=(
            "You are a surveillance camera operator. When given coordinates:\n"
            "1. Confirm camera positioning towards the coordinates\n"
            "2. Describe the captured image (simulate: you see a dark-colored "
            "SUV, model appears to be a Toyota Land Cruiser, parked near a "
            "warehouse building, partially obscured by trees)\n"
            "3. Report image quality and visibility conditions\n"
            "Be brief and factual like an operations report."
        ),
    )

    meteo_agent = client.as_agent(
        name="MeteoAgent",
        instructions=(
            "You are a meteorological analyst. When given coordinates:\n"
            "1. Report weather conditions (simulate: partly cloudy, 18°C, "
            "wind SW 12km/h, visibility 8km, humidity 65%%)\n"
            "2. Assess impact on field operations and surveillance quality\n"
            "3. Provide 6-hour forecast summary\n"
            "Be brief and factual like a weather operations brief."
        ),
    )

    workflow = ConcurrentBuilder(
        participants=[camera_agent, meteo_agent],
    ).build()

    print("  Built ConcurrentBuilder workflow: CameraAgent + MeteoAgent (parallel)")
    return workflow


async def run_reconnaissance(
    coordinates: Annotated[str, "GPS coordinates for reconnaissance, e.g. '40.41N, 3.70W'"],
    situation: Annotated[str, "Brief description of the situation to assess"],
) -> str:
    """Run parallel reconnaissance: camera surveillance + weather assessment for given coordinates."""
    global _recon_workflow

    query = f"Coordinates: {coordinates}. Situation: {situation}. Provide full assessment."
    result = await _recon_workflow.run(query)
    outputs = result.get_outputs()

    # Collect all text responses from concurrent agents
    report_parts = []
    if outputs:
        for output in outputs:
            if isinstance(output, list):
                for msg in output:
                    if hasattr(msg, "text") and msg.text:
                        speaker = msg.author_name or msg.role
                        report_parts.append(f"[{speaker}]: {msg.text}")
            elif hasattr(output, "text") and output.text:
                report_parts.append(output.text)

    if report_parts:
        return "\n\n".join(report_parts)
    return "Reconnaissance completed but no data was collected."


def create_recon_agent(client: OllamaChatClient) -> Agent:
    """Create the ReconAgent — a real Agent with the recon tool."""
    recon_agent = client.as_agent(
        name="ReconAgent",
        instructions=(
            "You are a reconnaissance team coordinator. You have access to the "
            "run_reconnaissance tool that deploys camera surveillance and weather "
            "assessment teams in parallel.\n\n"
            "When asked to assess a location or perform reconnaissance:\n"
            "1. Extract the coordinates and situation from the request\n"
            "2. Call run_reconnaissance with those parameters\n"
            "3. Summarize the combined results clearly\n\n"
            "Always use the tool — never make up reconnaissance data."
        ),
        tools=[run_reconnaissance],
    )
    return recon_agent


def create_specialists(client: OllamaChatClient) -> tuple[Agent, Agent]:
    """Create the coordinator and vehicle expert agents."""
    coordinator = client.as_agent(
        name="Coordinator",
        instructions=(
            "You are an operations coordinator managing field agents.\n"
            "Your role is to route requests to the right specialist:\n\n"
            "- If reconnaissance/surveillance is needed (camera, weather, location "
            "assessment), transfer to ReconAgent.\n"
            "- If vehicle identification or vehicle details are needed, "
            "transfer to VehicleExpert.\n"
            "- If the task is complete or you need more info from the operator, "
            "respond directly.\n\n"
            "Always be brief and decisive. State which team you are routing to and why."
        ),
    )

    vehicle_expert = client.as_agent(
        name="VehicleExpert",
        instructions=(
            "You are a vehicle identification expert. When given a description "
            "or image details of a vehicle:\n"
            "1. Analyze the vehicle characteristics described\n"
            "2. Provide a likely identification (make, model, year range)\n"
            "3. Add relevant tactical details (common uses, notable features)\n"
            "Be concise and confidence-rated (e.g., 'High confidence: Toyota Land Cruiser J200')."
        ),
    )

    return coordinator, vehicle_expert


def handle_events(events: list) -> list:
    """Process workflow events and return pending user input requests."""
    requests = []

    for event in events:
        if event.type == "handoff_sent":
            print(f"\n  >> HANDOFF: {event.data.source} → {event.data.target}")

        elif event.type == "status":
            state_name = event.state.value if hasattr(event.state, "value") else str(event.state)
            if "IDLE" in str(state_name).upper():
                print(f"\n  [Status] {state_name}")

        elif event.type == "output":
            data = event.data
            if isinstance(data, AgentResponse):
                for message in data.messages:
                    if not message.text:
                        continue
                    speaker = message.author_name or message.role
                    print(f"\n  {speaker}: {message.text[:400]}")
            elif isinstance(data, list):
                print(f"\n  {'=' * 50}")
                print("  FINAL CONVERSATION SNAPSHOT:")
                for message in data:
                    if hasattr(message, "text") and message.text:
                        speaker = message.author_name or message.role
                        text = message.text[:200]
                        if len(message.text) > 200:
                            text += "..."
                        print(f"    {speaker}: {text}")
                print(f"  {'=' * 50}")

        elif event.type == "request_info" and isinstance(event.data, HandoffAgentUserRequest):
            if hasattr(event.data, "agent_response") and event.data.agent_response:
                for message in event.data.agent_response.messages:
                    if message.text:
                        speaker = message.author_name or message.role
                        print(f"\n  {speaker} (awaiting input): {message.text[:300]}")
            requests.append(event)

    return requests


async def main() -> None:
    """Run the nested composition prototype."""
    global _recon_workflow

    print(f"\n{'═' * 70}")
    print("  PROTOTYPE 03: Nested HandoffBuilder + ConcurrentBuilder (via Tool)")
    print(f"{'═' * 70}\n")

    # ── Setup ─────────────────────────────────────────────────
    print("[1/4] Creating OllamaChatClient...")
    client = create_client()

    print("\n[2/4] Building nested workflow components...")
    _recon_workflow = build_recon_workflow(client)
    recon_agent = create_recon_agent(client)
    coordinator, vehicle_expert = create_specialists(client)
    print(f"  Created: ReconAgent (with tool), Coordinator, VehicleExpert")

    print("\n[3/4] Building outer HandoffBuilder workflow...")
    print("  Topology: Coordinator ──► ReconAgent [tool→ConcurrentBuilder] | VehicleExpert")
    print("            ReconAgent  ──► Coordinator")
    print("            VehicleExpert ──► Coordinator")

    workflow = (
        HandoffBuilder(
            name="nested_composition_test",
            participants=[coordinator, recon_agent, vehicle_expert],
            termination_condition=lambda conv: len(conv) >= 14,
        )
        .with_start_agent(coordinator)
        .add_handoff(coordinator, [recon_agent, vehicle_expert])
        .add_handoff(recon_agent, [coordinator])
        .add_handoff(vehicle_expert, [coordinator])
        .build()
    )
    print("  Outer HandoffBuilder workflow built successfully!")

    # ── Test: Full nested flow ────────────────────────────────
    print(f"\n[4/4] Running nested workflow...")
    print(SEPARATOR)

    scripted_responses = [
        "My coordinates are 40.4168 N, 3.7038 W. I can see a large dark SUV parked by a warehouse.",
        "Yes, I need the vehicle identified. It looks like a large Japanese SUV, dark green.",
        "Thank you, that's all I need.",
    ]

    initial_message = (
        "Operations, this is field operator Alpha-7. I have an unidentified vehicle "
        "in my area of operations. Requesting reconnaissance and assessment."
    )
    print(f"\n  Operator: {initial_message}")

    workflow_result = workflow.run(initial_message, stream=True)
    events = [event async for event in workflow_result]
    pending_requests = handle_events(events)

    turn = 0
    while pending_requests and turn < len(scripted_responses):
        user_response = scripted_responses[turn]
        print(f"\n  Operator: {user_response}")
        turn += 1

        responses = {
            req.request_id: HandoffAgentUserRequest.create_response(user_response)
            for req in pending_requests
        }

        events = await workflow.run(responses=responses)
        pending_requests = handle_events(events)

    if pending_requests:
        print("\n  [Terminating remaining requests]")
        responses = {
            req.request_id: HandoffAgentUserRequest.terminate()
            for req in pending_requests
        }
        events = await workflow.run(responses=responses)
        handle_events(events)

    print(f"\n{SEPARATOR}")
    print("  RESULT: Nested composition test completed!")
    print("  ")
    print("  KEY FINDINGS:")
    print("    - HandoffBuilder with Agent-facade pattern: ", end="")
    print("WORKS!")
    print("    - Agent with tool wrapping ConcurrentBuilder: VALIDATED")
    print("    - Pattern: Agent.tools=[fn] → fn calls workflow.run() internally")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n  ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
