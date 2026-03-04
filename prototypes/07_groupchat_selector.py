"""
Prototype 07: GroupChatBuilder with Stateful Python Selector
=============================================================
Uses GroupChatBuilder with a pure-Python selection function (no LLM
for routing). The selector tracks conversation state and decides
which specialist speaks next based on keywords and turn history.

Participants: CaseManager, FieldSpecialist (no Orchestrator needed —
the Python selector does the routing).

Multi-turn: Each operator message triggers a new workflow.run() with
the full conversation history injected as context.

Run:
    OLLAMA_MODEL_ID=qwen3.5:4b python prototypes/07_groupchat_selector.py
"""

import asyncio
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_framework import AgentResponse
from agent_framework.orchestrations import GroupChatBuilder, GroupChatState

from shared_agents import (
    SEP,
    create_case_manager,
    create_field_specialist,
    get_client,
    print_agent_message,
    print_config,
)


# ── Stateful Python selector ─────────────────────────────────

CASE_KEYWORDS = re.compile(
    r"caso|case|crear caso|create case|cerrar|close|prioridad|priority|"
    r"estado del caso|case status|incidente|incident|actualiz|update|bms",
    re.IGNORECASE,
)

FIELD_KEYWORDS = re.compile(
    r"reconocimiento|recon|cámara|camera|clima|weather|vehículo|vehicle|"
    r"coordenadas|coordinates|posición|position|vigilancia|surveillance|"
    r"observa|evalua|assess|sensor|helo|aproximación",
    re.IGNORECASE,
)


class SelectorState:
    """Tracks conversation state to drive selector decisions."""

    def __init__(self):
        self.case_created = False
        self.field_done = False
        self.last_speaker: str | None = None
        self.turn_in_round = 0

    def reset_round(self):
        """Reset per-round state when a new operator message arrives."""
        self.turn_in_round = 0


_selector_state = SelectorState()


def select_next_speaker(state: GroupChatState) -> str:
    """Pure Python selector — decides which agent speaks next.

    Logic:
    - First round of a new report: CaseManager first, then FieldSpecialist
    - Subsequent turns: keyword-based routing
    - After FieldSpecialist → CaseManager (to update the case with findings)
    - Default: FieldSpecialist
    """
    global _selector_state
    participants = list(state.participants.keys())
    s = _selector_state

    # Get last message text for keyword analysis
    last_text = ""
    last_author = ""
    if state.conversation:
        last_msg = state.conversation[-1]
        last_text = (last_msg.text or "").lower()
        last_author = last_msg.author_name or last_msg.role or ""

    s.turn_in_round += 1

    # Rule 1: After FieldSpecialist responded → CaseManager updates the case
    if s.last_speaker == "FieldSpecialist" and not s.field_done:
        # Check if field gave a real assessment (not just asking for coords)
        if "?" not in last_text and len(last_text) > 100:
            s.field_done = True
            s.last_speaker = "CaseManager"
            print(f"  [SELECTOR] -> CaseManager (update case with field findings)")
            return "CaseManager"

    # Rule 2: New situation — no case created yet → CaseManager first
    if not s.case_created and s.turn_in_round == 1:
        s.case_created = True
        s.last_speaker = "CaseManager"
        print(f"  [SELECTOR] -> CaseManager (create case)")
        return "CaseManager"

    # Rule 3: After CaseManager on first round → FieldSpecialist
    if s.last_speaker == "CaseManager" and s.turn_in_round == 2 and not s.field_done:
        s.last_speaker = "FieldSpecialist"
        print(f"  [SELECTOR] -> FieldSpecialist (field assessment)")
        return "FieldSpecialist"

    # Rule 4: Explicit case keywords → CaseManager
    if CASE_KEYWORDS.search(last_text) and not FIELD_KEYWORDS.search(last_text):
        s.last_speaker = "CaseManager"
        print(f"  [SELECTOR] -> CaseManager (keyword match)")
        return "CaseManager"

    # Rule 5: Explicit field keywords or coordinates → FieldSpecialist
    if FIELD_KEYWORDS.search(last_text):
        s.last_speaker = "FieldSpecialist"
        s.field_done = False  # Reset — new field task
        print(f"  [SELECTOR] -> FieldSpecialist (keyword match)")
        return "FieldSpecialist"

    # Rule 6: If operator gave short numeric/coordinate response → FieldSpecialist
    if last_author == "user" and re.search(r"\d+\.?\d*", last_text):
        s.last_speaker = "FieldSpecialist"
        print(f"  [SELECTOR] -> FieldSpecialist (coordinates detected)")
        return "FieldSpecialist"

    # Default: FieldSpecialist
    s.last_speaker = "FieldSpecialist"
    print(f"  [SELECTOR] -> FieldSpecialist (default)")
    return "FieldSpecialist"


# ── Build workflow ────────────────────────────────────────────

def build_groupchat(client):
    """Build GroupChatBuilder with Python selector — no LLM routing."""
    case_manager = create_case_manager(client)
    field_specialist = create_field_specialist(client)

    workflow = (
        GroupChatBuilder(
            participants=[case_manager, field_specialist],
            selection_func=select_next_speaker,
            max_rounds=3,
        )
        .build()
    )
    return workflow


# ── Event processing ──────────────────────────────────────────

def process_events(events):
    """Process events. Print agent messages. Return texts."""
    agent_texts = []
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
                        print_agent_message(speaker, msg.text)
                        agent_texts.append((speaker, msg.text))
            elif isinstance(data, list):
                for msg in data:
                    if hasattr(msg, "text") and msg.text:
                        key = f"{getattr(msg, 'author_name', '')}:{msg.text[:80]}"
                        if key in seen:
                            continue
                        seen.add(key)
                        speaker = getattr(msg, "author_name", None) or getattr(msg, "role", "?")
                        print_agent_message(speaker, msg.text)
                        agent_texts.append((speaker, msg.text))

    return agent_texts


# ── Main loop ─────────────────────────────────────────────────

async def main():
    print_config(
        "PROTOTYPE 07 — GroupChat with Python Selector",
        "GroupChatBuilder + stateful selection_func | Routing: pure Python (no LLM routing)",
    )
    print("  Type /quit to exit.")

    client = get_client()

    # Conversation history across turns
    conversation_history: list[tuple[str, str]] = []  # (role, text)
    all_agent_texts: list[tuple[str, str]] = []

    print(f"\n{SEP}")
    print("\n  OPERATOR (you): ", end="", flush=True)
    initial = input().strip()
    if not initial or initial == "/quit":
        print("  Session ended.")
        return

    conversation_history.append(("Operador", initial))

    while True:
        print(f"\n  Processing...\n")

        # Reset per-round selector state
        _selector_state.reset_round()

        # Build fresh workflow each turn
        workflow = build_groupchat(client)

        # Build full context from conversation history
        full_context = "\n".join(
            f"{role}: {text}" for role, text in conversation_history
        )

        # Run workflow
        result = workflow.run(full_context, stream=True)
        events = [event async for event in result]
        print(f"  ({len(events)} events)")
        agent_texts = process_events(events)
        all_agent_texts.extend(agent_texts)

        # Add agent responses to conversation history
        for speaker, text in agent_texts:
            conversation_history.append((speaker, text))

        # Next operator turn
        print(f"\n{SEP}")
        print("\n  OPERATOR (you): ", end="", flush=True)
        user_input = input().strip()

        if not user_input or user_input == "/quit":
            break

        conversation_history.append(("Operador", user_input))

    print(f"\n{SEP}")
    print(f"  Done. Messages: {len(all_agent_texts)}")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
