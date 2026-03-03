"""
BMS Operations Runner
======================
Entry point for the 3-level multi-agent BMS system.

Modes:
  - Interactive (default): HITL via stdin — operator types messages.
  - Scripted (``--demo``):  Pre-scripted scenario for automated testing.

Usage:
    python -m src.runner                   # Interactive mode
    python -m src.runner --demo            # Scripted demo
    OLLAMA_HOST=http://bms-ollama:11434 python -m src.runner --demo
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from agent_framework import AgentResponse
from agent_framework.orchestrations import HandoffAgentUserRequest

from src.client import get_client
from src.config import OLLAMA_HOST, OLLAMA_MODEL_ID
from src.workflows.operations import build_operations_workflow

# ── Display ───────────────────────────────────────────────────
SEPARATOR = "─" * 70
BOLD_SEP = "═" * 70


def print_banner() -> None:
    """Print startup banner."""
    print(f"\n{BOLD_SEP}")
    print("  BMS OPERATIONS — Multi-Agent System")
    print(f"  Architecture: 3-level nested (HandoffBuilder + ConcurrentBuilder)")
    print(f"  Ollama:  {OLLAMA_HOST}  |  Model: {OLLAMA_MODEL_ID}")
    print(f"{BOLD_SEP}\n")


# ── Event processing ─────────────────────────────────────────

def process_events(events: list[Any]) -> list[Any]:
    """Process workflow events, print outputs, return pending HITL requests."""
    requests: list[Any] = []
    seen_texts: set[str] = set()  # Deduplicate messages

    for event in events:
        if event.type == "handoff_sent":
            src = event.data.source
            tgt = event.data.target
            print(f"\n  >> HANDOFF: {src} → {tgt}")

        elif event.type == "output":
            data = event.data
            if isinstance(data, AgentResponse):
                for message in data.messages:
                    if not message.text:
                        continue
                    key = f"{message.author_name}:{message.text[:100]}"
                    if key in seen_texts:
                        continue
                    seen_texts.add(key)
                    speaker = message.author_name or message.role
                    print(f"\n  [{speaker}]: {message.text[:500]}")
            elif isinstance(data, list):
                # Final conversation snapshot
                print(f"\n  {'=' * 50}")
                print("  CONVERSATION SNAPSHOT:")
                for message in data:
                    if hasattr(message, "text") and message.text:
                        speaker = getattr(message, "author_name", None) or getattr(message, "role", "agent")
                        text = message.text[:200]
                        if len(message.text) > 200:
                            text += "..."
                        print(f"    {speaker}: {text}")
                print(f"  {'=' * 50}")

        elif event.type == "request_info" and isinstance(event.data, HandoffAgentUserRequest):
            # Print the agent's message that precedes the user request
            if hasattr(event.data, "agent_response") and event.data.agent_response:
                for message in event.data.agent_response.messages:
                    if message.text:
                        key = f"{message.author_name}:{message.text[:100]}"
                        if key in seen_texts:
                            continue
                        seen_texts.add(key)
                        speaker = message.author_name or message.role
                        print(f"\n  [{speaker}]: {message.text[:500]}")
            requests.append(event)

    return requests


# ── Interactive mode ──────────────────────────────────────────

async def run_interactive(workflow: Any) -> None:
    """Run the BMS system in interactive HITL mode."""
    print("  Mode: INTERACTIVE  —  Type messages as a field operator.")
    print("  Commands: /quit to exit, /status for system info")
    print(SEPARATOR)

    # Get initial message from operator
    print("\n  Operator (you): ", end="", flush=True)
    initial = input().strip()
    if not initial or initial == "/quit":
        print("  Exiting.")
        return

    print(f"\n  [Sending to Orchestrator...]")
    result = workflow.run(initial, stream=True)
    events = [event async for event in result]
    pending = process_events(events)

    # HITL loop
    while pending:
        print(f"\n  Operator (you): ", end="", flush=True)
        user_input = input().strip()

        if user_input == "/quit":
            print("  Terminating session...")
            responses = {
                req.request_id: HandoffAgentUserRequest.terminate()
                for req in pending
            }
            events = await workflow.run(responses=responses)
            process_events(events)
            break

        if user_input == "/status":
            print(f"  Pending requests: {len(pending)}")
            print(f"  Ollama: {OLLAMA_HOST} | Model: {OLLAMA_MODEL_ID}")
            continue

        if not user_input:
            continue

        # Send response for all pending requests
        responses = {
            req.request_id: HandoffAgentUserRequest.create_response(user_input)
            for req in pending
        }
        events = await workflow.run(responses=responses)
        pending = process_events(events)

    print(f"\n{SEPARATOR}")
    print("  Session ended.\n")


# ── Demo mode ─────────────────────────────────────────────────

DEMO_SCENARIO = [
    (
        "Operations, this is Alpha-7. I have an unidentified vehicle in my "
        "AO near coordinates 40.4168N, 3.7038W. Requesting reconnaissance "
        "and vehicle identification."
    ),
    (
        "Coordinates confirmed: 40.4168 North, 3.7038 West. The vehicle is "
        "a large dark-green SUV, appears to be a Japanese make, parked next "
        "to a warehouse. I need a weather check too — considering helo approach."
    ),
    (
        "Roger. Create a case for this incident — priority HIGH. Mark it as "
        "possible hostile surveillance."
    ),
    "Thank you, that's all. Alpha-7 out.",
]


async def run_demo(workflow: Any) -> None:
    """Run a scripted demo scenario."""
    print("  Mode: DEMO  —  Running pre-scripted BMS scenario.")
    print(SEPARATOR)

    initial = DEMO_SCENARIO[0]
    print(f"\n  Operator: {initial}")

    result = workflow.run(initial, stream=True)
    events = [event async for event in result]
    pending = process_events(events)

    turn = 1
    while pending and turn < len(DEMO_SCENARIO):
        user_response = DEMO_SCENARIO[turn]
        print(f"\n  Operator: {user_response}")
        turn += 1

        responses = {
            req.request_id: HandoffAgentUserRequest.create_response(user_response)
            for req in pending
        }
        events = await workflow.run(responses=responses)
        pending = process_events(events)

    # Terminate any remaining requests
    if pending:
        print("\n  [Auto-terminating remaining requests]")
        responses = {
            req.request_id: HandoffAgentUserRequest.terminate()
            for req in pending
        }
        events = await workflow.run(responses=responses)
        process_events(events)

    print(f"\n{SEPARATOR}")
    print("  Demo scenario completed.")
    print(f"{BOLD_SEP}\n")


# ── Main ──────────────────────────────────────────────────────

async def main(demo: bool = False) -> None:
    """Build and run the full BMS Operations system."""
    print_banner()

    print("[1/2] Building 3-level workflow...")
    print("  L3: HandoffBuilder (Orchestrator → CaseManager | FieldSpecialist)")
    print("  L2:   └─ FieldSpecialist facade → HandoffBuilder (FieldCoord → Recon | Vehicle)")
    print("  L1:       └─ ReconAgent facade → ConcurrentBuilder (Camera ∥ Meteo)")

    client = get_client()
    workflow = build_operations_workflow(client)

    print("  All workflows built successfully!\n")
    print("[2/2] Starting BMS Operations...\n")

    if demo:
        await run_demo(workflow)
    else:
        await run_interactive(workflow)


def cli() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="BMS Operations — Multi-Agent System")
    parser.add_argument("--demo", action="store_true", help="Run scripted demo instead of interactive mode")
    args = parser.parse_args()

    try:
        asyncio.run(main(demo=args.demo))
    except KeyboardInterrupt:
        print("\n  Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n  ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
