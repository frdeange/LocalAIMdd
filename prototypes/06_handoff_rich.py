"""
Prototype 06: HandoffBuilder with Rich Topology
=================================================
Tests HandoffBuilder with qwen3.5:4b and an all-to-all handoff topology
where specialists can transfer directly to each other (not only via
the Orchestrator).

Topology:
    Orchestrator → [CaseManager, FieldSpecialist]
    FieldSpecialist → [CaseManager, Orchestrator]
    CaseManager → [FieldSpecialist, Orchestrator]

CaseManager runs in autonomous mode (creates cases without asking the
operator). FieldSpecialist uses normal HITL — when it needs coordinates
it returns to the Orchestrator who relays to the operator.

Run:
    OLLAMA_MODEL_ID=qwen3.5:4b python prototypes/06_handoff_rich.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_framework import AgentResponse
from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

from shared_agents import (
    SEP,
    create_case_manager,
    create_field_specialist,
    create_orchestrator,
    get_client,
    print_agent_message,
    print_config,
    print_handoff,
)


# ── Build workflow ────────────────────────────────────────────

def build_workflow(client):
    """Build L3 HandoffBuilder with rich all-to-all topology."""
    orchestrator = create_orchestrator(client)
    case_manager = create_case_manager(client)
    field_specialist = create_field_specialist(client)

    workflow = (
        HandoffBuilder(
            name="bms_operations_06",
            participants=[orchestrator, case_manager, field_specialist],
            termination_condition=lambda conv: len(conv) >= 30,
        )
        .with_start_agent(orchestrator)
        # Rich topology — all agents can transfer to all others
        .add_handoff(orchestrator, [case_manager, field_specialist])
        .add_handoff(field_specialist, [case_manager, orchestrator])
        .add_handoff(case_manager, [field_specialist, orchestrator])
        # CaseManager runs autonomously: after tool calls it gets
        # extra turns to invoke the handoff tool to FieldSpecialist.
        # FieldSpecialist is NOT autonomous — uses HITL. Empty first
        # responses are handled by auto-retry in the event loop.
        .with_autonomous_mode(
            agents=[case_manager],
            turn_limits={"CaseManager": 3},
        )
        .build()
    )
    return workflow


# ── Event processing ──────────────────────────────────────────

def process_events(events, debug=False):
    """Process workflow events. Print messages. Return pending HITL requests."""
    agent_texts = []
    pending = []
    seen = set()

    for event in events:
        if debug:
            data_summary = type(event.data).__name__
            if hasattr(event.data, 'text') and event.data.text:
                data_summary += f" text={event.data.text[:60]!r}"
            elif hasattr(event.data, 'agent_response'):
                ar = event.data.agent_response
                msgs = [m.text[:40] for m in ar.messages if m.text] if ar and ar.messages else []
                data_summary += f" msgs={msgs}"
            print(f"  [DBG] event.type={event.type!r} data={data_summary}")

        if event.type == "handoff_sent":
            print_handoff(event.data.source, event.data.target)

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
                        print_agent_message(speaker, msg.text)
                        agent_texts.append(msg.text)
            elif isinstance(data, list):
                # Final conversation snapshot
                print(f"\n  {'=' * 50}")
                print("  CONVERSATION SNAPSHOT:")
                for msg in data:
                    if hasattr(msg, "text") and msg.text:
                        speaker = getattr(msg, "author_name", None) or getattr(msg, "role", "?")
                        print(f"    {speaker}: {msg.text[:200]}")
                print(f"  {'=' * 50}")

        elif event.type == "request_info" and isinstance(
            event.data, HandoffAgentUserRequest
        ):
            has_text = False
            if event.data.agent_response:
                for msg in event.data.agent_response.messages:
                    if msg.text:
                        key = f"{msg.author_name}:{msg.text[:80]}"
                        if key in seen:
                            has_text = True  # Already shown via output event
                            continue
                        seen.add(key)
                        speaker = msg.author_name or msg.role
                        print_agent_message(speaker, msg.text)
                        agent_texts.append(msg.text)
                        has_text = True
            if not has_text and not agent_texts:
                # No text shown at all in this batch — truly empty response.
                print("\n  [Sistema]: El agente está listo. Proporcione información adicional.")
            pending.append(event)

    return agent_texts, pending


# ── Main loop ─────────────────────────────────────────────────

async def main():
    print_config(
        "PROTOTYPE 06 — HandoffBuilder Rich Topology",
        "HandoffBuilder + all-to-all handoffs | CaseManager: autonomous | FieldSpecialist: HITL",
    )
    print("  Type /quit to exit.")

    client = get_client()
    print(f"\n  Building workflow... ", end="", flush=True)
    workflow = build_workflow(client)
    print("OK\n")
    print(SEP)

    # Initial message
    print("\n  OPERATOR (you): ", end="", flush=True)
    initial = input().strip()
    if not initial or initial == "/quit":
        print("  Session ended.")
        return

    print(f"\n  Processing...\n")

    result = workflow.run(initial, stream=True)
    events = [event async for event in result]
    agent_texts, pending = process_events(events, debug=True)

    # Auto-retry: if FieldSpecialist produced empty response, nudge it
    if pending and not agent_texts:
        print("\n  [auto-retry: empty agent response, nudging...]\n")
        responses = {
            req.request_id: HandoffAgentUserRequest.create_response(
                "Operador esperando. Proporcione su respuesta."
            )
            for req in pending
        }
        events = await workflow.run(responses=responses)
        new_texts, pending = process_events(events, debug=True)
        agent_texts.extend(new_texts)

    # HITL loop
    while pending:
        print(f"\n{SEP}")
        print("\n  OPERATOR (you): ", end="", flush=True)
        user_input = input().strip()

        if not user_input:
            continue

        if user_input == "/quit":
            print("\n  Terminating...")
            responses = {
                req.request_id: HandoffAgentUserRequest.terminate()
                for req in pending
            }
            events = await workflow.run(responses=responses)
            process_events(events)
            break

        print(f"\n  Processing...\n")

        responses = {
            req.request_id: HandoffAgentUserRequest.create_response(user_input)
            for req in pending
        }
        events = await workflow.run(responses=responses)
        new_texts, pending = process_events(events, debug=True)
        agent_texts.extend(new_texts)

        # Auto-retry: if agent produced empty response after user input, nudge it
        if pending and not new_texts:
            print("\n  [auto-retry: empty agent response, nudging...]\n")
            responses = {
                req.request_id: HandoffAgentUserRequest.create_response(
                    "Operador esperando. Proporcione su respuesta."
                )
                for req in pending
            }
            events = await workflow.run(responses=responses)
            retry_texts, pending = process_events(events, debug=True)
            agent_texts.extend(retry_texts)

    print(f"\n{SEP}")
    print(f"  Done. Messages received: {len(agent_texts)}")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
