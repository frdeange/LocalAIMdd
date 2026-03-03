"""
Prototype 01 — HandoffBuilder Basic with OllamaChatClient
==========================================================
Validates that HandoffBuilder works with a local Ollama SLM.

Creates 3 agents:
  - Coordinator: receives user input, routes to specialists
  - IncidentAgent: handles incident/case creation
  - InfoAgent: handles information requests

The coordinator should route based on the user's message.
We test the full request/response cycle including the HITL pattern
(HandoffAgentUserRequest).

Usage:
    python prototypes/01_handoff_basic.py

Environment:
    OLLAMA_HOST      (default: http://localhost:11434)
    OLLAMA_MODEL_ID  (default: qwen2.5:3b)
"""

import asyncio
import os
import sys
from typing import cast

import patch_ollama  # noqa: F401 — must import before using OllamaChatClient

from agent_framework import Agent, AgentResponse, Message, WorkflowRunState
from agent_framework.ollama import OllamaChatClient
from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

# ── Config ────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL_ID = os.getenv("OLLAMA_MODEL_ID", "qwen2.5:3b")

SEPARATOR = "─" * 70


def create_client() -> OllamaChatClient:
    """Create an OllamaChatClient pointing to local Ollama."""
    print(f"  Ollama host:  {OLLAMA_HOST}")
    print(f"  Model:        {OLLAMA_MODEL_ID}")
    return OllamaChatClient(host=OLLAMA_HOST, model_id=OLLAMA_MODEL_ID)


def create_agents(client: OllamaChatClient) -> tuple[Agent, Agent, Agent]:
    """Create coordinator and specialist agents."""
    coordinator = client.as_agent(
        name="Coordinator",
        instructions=(
            "You are a coordinator that routes requests to the right specialist.\n"
            "- If the user reports an incident, problem, or wants to open a case, "
            "transfer to IncidentAgent.\n"
            "- If the user asks for information, details, or identification, "
            "transfer to InfoAgent.\n"
            "- If you are unsure, ask the user for clarification.\n"
            "Always be brief and direct."
        ),
    )

    incident_agent = client.as_agent(
        name="IncidentAgent",
        instructions=(
            "You are an incident management specialist. When you receive a request:\n"
            "1. Acknowledge the incident\n"
            "2. Create a brief incident summary\n"
            "3. Ask the user if they need anything else\n"
            "Be concise and professional."
        ),
    )

    info_agent = client.as_agent(
        name="InfoAgent",
        instructions=(
            "You are an information specialist. When you receive a request:\n"
            "1. Acknowledge what information is needed\n"
            "2. Provide a brief response based on what you know\n"
            "3. Ask if the user needs more details\n"
            "Be concise and helpful."
        ),
    )

    return coordinator, incident_agent, info_agent


def handle_events(events: list) -> list:
    """Process workflow events and return pending user input requests."""
    requests = []

    for event in events:
        if event.type == "handoff_sent":
            print(f"\n  >> HANDOFF: {event.data.source} → {event.data.target}")

        elif event.type == "status":
            state_name = event.state.value if hasattr(event.state, "value") else str(event.state)
            print(f"\n  [Status] {state_name}")

        elif event.type == "output":
            data = event.data
            if isinstance(data, AgentResponse):
                for message in data.messages:
                    if not message.text:
                        continue
                    speaker = message.author_name or message.role
                    print(f"\n  {speaker}: {message.text}")
            elif isinstance(data, list):
                # Final conversation snapshot
                print(f"\n  {'=' * 50}")
                print("  FINAL CONVERSATION:")
                for message in data:
                    if hasattr(message, "text") and message.text:
                        speaker = message.author_name or message.role
                        print(f"    {speaker}: {message.text[:200]}")
                print(f"  {'=' * 50}")

        elif event.type == "request_info" and isinstance(event.data, HandoffAgentUserRequest):
            # Agent is requesting user input
            if hasattr(event.data, "agent_response") and event.data.agent_response:
                for message in event.data.agent_response.messages:
                    if message.text:
                        speaker = message.author_name or message.role
                        print(f"\n  {speaker} (requesting input): {message.text}")
            requests.append(event)

    return requests


async def main() -> None:
    """Run the HandoffBuilder prototype."""
    print(f"\n{'═' * 70}")
    print("  PROTOTYPE 01: HandoffBuilder Basic")
    print(f"{'═' * 70}\n")

    # ── Setup ─────────────────────────────────────────────────
    print("[1/4] Creating OllamaChatClient...")
    client = create_client()

    print("\n[2/4] Creating agents...")
    coordinator, incident_agent, info_agent = create_agents(client)
    print("  Created: Coordinator, IncidentAgent, InfoAgent")

    print("\n[3/4] Building HandoffBuilder workflow...")
    workflow = (
        HandoffBuilder(
            name="basic_handoff_test",
            participants=[coordinator, incident_agent, info_agent],
            # Stop when conversation has 8+ messages (reasonable for a test)
            termination_condition=lambda conv: len(conv) >= 8,
        )
        .with_start_agent(coordinator)
        .add_handoff(coordinator, [incident_agent, info_agent])
        .add_handoff(incident_agent, [coordinator])
        .add_handoff(info_agent, [coordinator])
        .build()
    )
    print("  Workflow built successfully")

    # ── Test: Incident routing ────────────────────────────────
    print(f"\n[4/4] Running workflow...")
    print(SEPARATOR)

    scripted_responses = [
        "I found an unidentified vehicle near my position at coordinates 40.41, -3.70.",
        "That's all for now, thank you.",
    ]

    initial_message = "I need to report an incident. There's a suspicious vehicle in my area."
    print(f"\n  User: {initial_message}")

    # Start the workflow
    workflow_result = workflow.run(initial_message, stream=True)
    events = [event async for event in workflow_result]
    pending_requests = handle_events(events)

    # Process request/response cycles
    turn = 0
    while pending_requests and turn < len(scripted_responses):
        user_response = scripted_responses[turn]
        print(f"\n  User: {user_response}")
        turn += 1

        responses = {
            req.request_id: HandoffAgentUserRequest.create_response(user_response)
            for req in pending_requests
        }

        events = await workflow.run(responses=responses)
        pending_requests = handle_events(events)

    # Terminate if still pending
    if pending_requests:
        print("\n  [Terminating remaining requests]")
        responses = {
            req.request_id: HandoffAgentUserRequest.terminate()
            for req in pending_requests
        }
        events = await workflow.run(responses=responses)
        handle_events(events)

    print(f"\n{SEPARATOR}")
    print("  RESULT: HandoffBuilder test completed successfully!")
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
