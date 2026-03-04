"""
Prototype 05: GroupChat with Selection Function
=================================================
Uses GroupChatBuilder with a selection function that uses an LLM
to decide which specialist speaks next.

Unlike orchestrator_agent mode (which requires structured JSON output
and is incompatible with Ollama), this uses a simple selection function
that calls the LLM directly to decide routing.

Agents:
  - CaseManager: creates/manages BMS cases via MCP
  - FieldSpecialist: recon via Camera + Weather MCP tools

Run:
    python prototypes/05_groupchat.py

Requires tunnels to Ollama + MCP services.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_framework import Agent, AgentResponse, MCPStreamableHTTPTool
from agent_framework.orchestrations import GroupChatBuilder, GroupChatState

from src.client import get_client

SEP = "-" * 60


# ── LLM-based selection function ─────────────────────────────
# Instead of orchestrator_agent (incompatible with Ollama structured output),
# we use a selection_func that calls the LLM directly to decide routing.

_selector_client = None


async def select_next_speaker(state: GroupChatState) -> str:
    """Use the LLM to decide which agent should speak next."""
    global _selector_client
    if _selector_client is None:
        _selector_client = get_client()

    participants = list(state.participants.keys())
    
    # Build a simple prompt for the LLM
    conv_summary = ""
    for msg in state.conversation[-6:]:  # Last 6 messages for context
        speaker = msg.author_name or msg.role
        text = (msg.text or "")[:150]
        conv_summary += f"  {speaker}: {text}\n"

    prompt = (
        f"You are a military operations coordinator. "
        f"Based on this conversation, which specialist should respond next?\n\n"
        f"Available specialists: {', '.join(participants)}\n\n"
        f"Recent conversation:\n{conv_summary}\n"
        f"Rules:\n"
        f"- New situation without a case: CaseManager\n"
        f"- Reconnaissance or assessment needed: FieldSpecialist\n"
        f"- If FieldSpecialist already responded with findings: CaseManager to update\n\n"
        f"Reply with ONLY the specialist name, nothing else."
    )

    response = await _selector_client.as_agent(
        name="_selector", instructions="Reply with only the agent name."
    ).run(prompt)

    # Extract the name from response
    result_text = ""
    if hasattr(response, 'text') and response.text:
        result_text = response.text.strip()
    elif hasattr(response, 'messages'):
        for msg in response.messages:
            if hasattr(msg, 'text') and msg.text:
                result_text = msg.text.strip()
                break

    # Match to a valid participant
    for name in participants:
        if name.lower() in result_text.lower():
            print(f"  [SELECTOR] -> {name}")
            return name

    # Default: first participant
    print(f"  [SELECTOR] -> {participants[0]} (default)")
    return participants[0]


def create_field_specialist(client):
    camera_mcp = MCPStreamableHTTPTool(
        name="camera_mcp", url="http://localhost:8090/mcp",
        description="Surveillance camera system",
    )
    weather_mcp = MCPStreamableHTTPTool(
        name="weather_mcp", url="http://localhost:8091/mcp",
        description="Weather station",
    )
    return client.as_agent(
        name="FieldSpecialist",
        instructions=(
            "You are a tactical field analyst. "
            "You have camera and weather sensors. "
            "You MUST have explicit coordinates before using any tool. "
            "If coordinates are missing, ask the operator. "
            "Once you have coordinates, use your tools and provide a 3-4 sentence "
            "tactical assessment. "
            "Sensor data is in English but respond in the operator's language. "
            "No markdown, plain text only."
        ),
        tools=[camera_mcp, weather_mcp],
    )


def create_case_manager(client):
    bms_mcp = MCPStreamableHTTPTool(
        name="bms_mcp", url="http://localhost:8093/mcp",
        description="BMS case management database",
    )
    return client.as_agent(
        name="CaseManager",
        instructions=(
            "You are a case management officer. "
            "When a new situation is reported, immediately create a case using your tools. "
            "Confirm the case ID to the operator. "
            "Respond in the same language as the operator. "
            "No markdown, plain text only."
        ),
        tools=[bms_mcp],
    )


def build_groupchat(client):
    field_specialist = create_field_specialist(client)
    case_manager = create_case_manager(client)

    workflow = (
        GroupChatBuilder(
            participants=[case_manager, field_specialist],
            selection_func=select_next_speaker,
            max_rounds=3,  # Each invocation does max 3 rounds (selector picks up to 3 agents)
        )
        .build()  # NO with_request_info — we manage turns ourselves
    )
    return workflow


def process_events(events):
    agent_texts = []
    pending = []
    seen = set()

    for event in events:
        if event.type == "output":
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

        elif event.type == "request_info":
            req_data = event.data
            # Try to extract the agent's message from the request
            for attr in ['response', 'agent_response']:
                resp = getattr(req_data, attr, None)
                if resp and hasattr(resp, 'messages'):
                    for msg in resp.messages:
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
            print(f"\n  [Esperando input del operador...]")

    return agent_texts, pending


async def main():
    print(SEP)
    print("  PROTOTIPO 05 - GroupChat con Selector LLM")
    print("  Escribe como operador de campo.")
    print("  Escribe /salir para terminar.")
    print(SEP)

    client = get_client()
    conversation_history = []

    print("\n  OPERADOR (tu): ", end="", flush=True)
    initial = input().strip()
    if not initial or initial == "/salir":
        print("  Sesion terminada.")
        return

    conversation_history.append(initial)
    all_agent_texts = []

    # Each operator message = build fresh workflow + run with full history
    while True:
        current_input = conversation_history[-1]
        print(f"\n  Procesando...\n")

        # Build fresh workflow each turn (stateful)
        workflow = build_groupchat(client)

        # Run with full conversation context
        full_context = "\n".join(
            f"{'Operador' if i % 2 == 0 else 'Agente'}: {msg}"
            for i, msg in enumerate(conversation_history)
        )

        result = workflow.run(full_context, stream=True)
        events = [event async for event in result]
        print(f"  ({len(events)} events)")
        agent_texts, _ = process_events(events)
        all_agent_texts.extend(agent_texts)

        if agent_texts:
            # Add last agent response to history
            conversation_history.append(agent_texts[-1])

        print(f"\n{SEP}")
        print("\n  OPERADOR (tu): ", end="", flush=True)
        user_input = input().strip()

        if not user_input or user_input == "/salir":
            break

        conversation_history.append(user_input)

    print(f"\n{SEP}")
    print(f"  Fin. Mensajes: {len(all_agent_texts)}")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
