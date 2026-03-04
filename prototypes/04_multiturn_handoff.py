"""
Prototype 04: Interactive Multi-turn Handoff (Self-contained)
==============================================================
Fully self-contained — creates its own agents and workflow.
Does NOT import from src/agents/ or src/workflows/.

Tests different instruction styles to find what works with qwen2.5:7b.

Run:
    python prototypes/04_multiturn_handoff.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_framework import Agent, AgentResponse, MCPStreamableHTTPTool
from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

# We only import the client factory and the patch
from src.client import get_client

SEP = "-" * 60


# ── Self-contained agents (experiment with instructions here) ──

def create_orchestrator(client):
    """Orchestrator — simple instructions, no tool name mentions."""
    return client.as_agent(
        name="Orchestrator",
        instructions=(
            "You are a military operations coordinator. "
            "You receive reports from field operators. "
            "Route reconnaissance and surveillance tasks to the field specialist. "
            "Route case management tasks to the case manager. "
            "If you need more information from the operator, ask directly. "
            "Always respond in the same language as the operator. "
            "Plain text only, no markdown."
        ),
    )


def create_field_specialist(client):
    """FieldSpecialist — simple agent with MCP recon tool."""
    camera_mcp = MCPStreamableHTTPTool(
        name="camera_mcp",
        url="http://localhost:8090/mcp",
        description="Surveillance camera system",
    )
    weather_mcp = MCPStreamableHTTPTool(
        name="weather_mcp",
        url="http://localhost:8091/mcp",
        description="Weather station",
    )
    return client.as_agent(
        name="FieldSpecialist",
        instructions=(
            "You are a tactical field analyst supporting military operations. "
            "You have camera and weather sensors. "
            "IMPORTANT: You MUST have explicit coordinates from the operator before using any tool. "
            "If the operator has NOT provided coordinates (latitude and longitude), "
            "your ONLY action is to ask for them. Do NOT assume or invent coordinates. "
            "Once you have coordinates, use your tools and provide a 3-4 sentence tactical assessment. "
            "CRITICAL: Your sensor tools return data in English, but you MUST ALWAYS "
            "respond in the SAME LANGUAGE the operator used. No markdown, plain text only."
        ),
        tools=[camera_mcp, weather_mcp],
    )


def create_case_manager(client):
    """CaseManager — simple agent with MCP BMS tool."""
    bms_mcp = MCPStreamableHTTPTool(
        name="bms_mcp",
        url="http://localhost:8093/mcp",
        description="BMS case management database",
    )
    return client.as_agent(
        name="CaseManager",
        instructions=(
            "You are a case management officer. "
            "You create and manage incident cases using your tools. "
            "Always respond in the same language as the request. "
            "Plain text only, no markdown."
        ),
        tools=[bms_mcp],
    )


def build_workflow(client):
    """Build the L3 HandoffBuilder workflow."""
    orchestrator = create_orchestrator(client)
    field_specialist = create_field_specialist(client)
    case_manager = create_case_manager(client)

    workflow = (
        HandoffBuilder(
            name="bms_operations",
            participants=[orchestrator, field_specialist, case_manager],
            termination_condition=lambda conv: len(conv) >= 30,
        )
        .with_start_agent(orchestrator)
        .add_handoff(orchestrator, [field_specialist, case_manager])
        .add_handoff(field_specialist, [orchestrator])
        .add_handoff(case_manager, [orchestrator])
        .build()
    )
    return workflow


# ── Event processing ───────────────────────────────────────────

def process_events(events):
    """Process events. Print agent messages. Return pending HITL events."""
    agent_texts = []
    pending = []
    seen = set()

    for event in events:
        if event.type == "handoff_sent":
            print(f"  >> HANDOFF: {event.data.source} -> {event.data.target}")

        elif event.type == "output":
            data = event.data
            if isinstance(data, AgentResponse):
                for msg in data.messages:
                    if msg.text:
                        key = f"{msg.author_name}:{msg.text[:80]}"
                        if key in seen:
                            continue
                        seen.add(key)
                        speaker = msg.author_name or msg.role
                        print(f"\n  AGENTE [{speaker}]:")
                        print(f"  {msg.text[:800]}")
                        agent_texts.append(msg.text)

        elif event.type == "request_info" and isinstance(
            event.data, HandoffAgentUserRequest
        ):
            if event.data.agent_response:
                for msg in event.data.agent_response.messages:
                    if msg.text:
                        key = f"{msg.author_name}:{msg.text[:80]}"
                        if key in seen:
                            continue
                        seen.add(key)
                        speaker = msg.author_name or msg.role
                        print(f"\n  AGENTE [{speaker}]:")
                        print(f"  {msg.text[:800]}")
                        agent_texts.append(msg.text)
            pending.append(event)

    return agent_texts, pending


# ── Main ──────────────────────────────────────────────────────

async def main():
    print(SEP)
    print("  PROTOTIPO 04 - Conversacion Interactiva")
    print("  (Autocontenido - agentes locales)")
    print("  Escribe /salir para terminar.")
    print(SEP)

    client = get_client()
    print(f"\n  Construyendo workflow... ", end="", flush=True)
    workflow = build_workflow(client)
    print("OK\n")
    print(SEP)

    print("\n  OPERADOR (tu): ", end="", flush=True)
    initial = input().strip()
    if not initial or initial == "/salir":
        print("  Sesion terminada.")
        return

    print(f"\n  Procesando...\n")

    result = workflow.run(initial, stream=True)
    events = [event async for event in result]
    agent_texts, pending = process_events(events)

    while pending:
        print(f"\n{SEP}")
        print("\n  OPERADOR (tu): ", end="", flush=True)
        user_input = input().strip()

        if not user_input:
            continue

        if user_input == "/salir":
            print("\n  Terminando...")
            responses = {
                req.request_id: HandoffAgentUserRequest.terminate()
                for req in pending
            }
            events = await workflow.run(responses=responses)
            process_events(events)
            break

        print(f"\n  Procesando...\n")

        responses = {
            req.request_id: HandoffAgentUserRequest.create_response(user_input)
            for req in pending
        }
        events = await workflow.run(responses=responses)
        new_texts, pending = process_events(events)
        agent_texts.extend(new_texts)

    print(f"\n{SEP}")
    print(f"  Fin. Mensajes recibidos: {len(agent_texts)}")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
