"""
Prototype 08: WorkflowBuilder with Custom Executor Router
===========================================================
Uses MAF's low-level WorkflowBuilder with a custom OpsRouter Executor
that controls all routing decisions in Python code. The LLM agents
only do specialist work (MCP tools, analysis), never routing.

Architecture:
    OpsRouter (start) ──edge──▶ CaseExec ──edge──▶ OpsRouter
    OpsRouter ──edge──▶ FieldExec ──edge──▶ OpsRouter

OpsRouter uses hybrid routing: regex keywords first, LLM classification
as fallback. HITL via ctx.request_info() for operator interaction.

Run:
    OLLAMA_MODEL_ID=qwen3.5:4b python prototypes/08_workflow_executor.py
"""

import asyncio
import re
import sys
import os
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_framework import (
    Agent,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentResponse,
    AgentResponseUpdate,
    Executor,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowEvent,
    handler,
    response_handler,
)

from shared_agents import (
    SEP,
    create_case_manager,
    create_field_specialist,
    get_client,
    print_agent_message,
    print_config,
)


# ── Typed messages for routing ────────────────────────────────

@dataclass
class CaseRequest:
    """Request for the CaseManager agent."""
    messages: list[Message]
    task_hint: str = ""  # "create", "update", etc.


@dataclass
class CaseResponse:
    """Response from the CaseManager agent."""
    text: str
    case_id: str | None = None


@dataclass
class FieldRequest:
    """Request for the FieldSpecialist agent."""
    messages: list[Message]


@dataclass
class FieldResponse:
    """Response from the FieldSpecialist agent."""
    text: str
    needs_input: bool = False  # True if agent is asking operator for info


@dataclass
class OperatorPrompt:
    """Request sent to the human operator."""
    prompt: str


# ── Keyword classification ────────────────────────────────────

CASE_KEYWORDS = re.compile(
    r"caso|case|crear caso|create case|cerrar|close|prioridad|priority|"
    r"estado del caso|case status|incidente|incident|actualiz|update|bms",
    re.IGNORECASE,
)

FIELD_KEYWORDS = re.compile(
    r"reconocimiento|recon|cámara|camera|clima|weather|vehículo|vehicle|"
    r"coordenadas|coordinates|posición|position|vigilancia|surveillance|"
    r"sensor|evaluación|assessment",
    re.IGNORECASE,
)

NEEDS_INPUT_PATTERNS = re.compile(
    r"\?|coordenadas|coordinates|proporcione|provide|necesito|need|"
    r"indique|specify|dónde|where|ubicación|location",
    re.IGNORECASE,
)


def classify_intent(text: str) -> str:
    """Classify operator message intent.

    Returns: 'case', 'field', 'new_report', or 'unknown'
    """
    has_case = bool(CASE_KEYWORDS.search(text))
    has_field = bool(FIELD_KEYWORDS.search(text))

    if has_case and not has_field:
        return "case"
    if has_field and not has_case:
        return "field"
    if has_case and has_field:
        return "both"
    # New situation report — no specific keywords
    return "new_report"


def response_needs_input(text: str) -> bool:
    """Heuristic: does the agent's response ask the operator for information?"""
    return bool(NEEDS_INPUT_PATTERNS.search(text)) and len(text) < 500


# ── CaseExec — wraps CaseManager agent ───────────────────────

class CaseExec(Executor):
    """Executor that wraps the CaseManager agent."""

    def __init__(self, agent: Agent):
        super().__init__(id="case_exec")
        self.agent = agent

    @handler
    async def on_request(
        self, request: CaseRequest, ctx: WorkflowContext[CaseResponse]
    ) -> None:
        """Run CaseManager agent and return response."""
        print(f"  [CaseExec] Running CaseManager...")
        response = await self.agent.run(request.messages)

        # Extract text from response
        text = ""
        if hasattr(response, "text") and response.text:
            text = response.text
        elif hasattr(response, "messages"):
            for msg in response.messages:
                if msg.text:
                    text = msg.text
                    break

        # Try to extract case ID from response
        case_id = None
        case_match = re.search(r"BMS-\d{4}-\d{3}", text)
        if case_match:
            case_id = case_match.group()

        print(f"  [CaseExec] Done. Case ID: {case_id or 'N/A'}")
        await ctx.send_message(CaseResponse(text=text, case_id=case_id))


# ── FieldExec — wraps FieldSpecialist agent ───────────────────

class FieldExec(Executor):
    """Executor that wraps the FieldSpecialist agent."""

    def __init__(self, agent: Agent):
        super().__init__(id="field_exec")
        self.agent = agent

    @handler
    async def on_request(
        self, request: FieldRequest, ctx: WorkflowContext[FieldResponse]
    ) -> None:
        """Run FieldSpecialist agent and return response."""
        print(f"  [FieldExec] Running FieldSpecialist...")
        response = await self.agent.run(request.messages)

        # Extract text from response
        text = ""
        if hasattr(response, "text") and response.text:
            text = response.text
        elif hasattr(response, "messages"):
            for msg in response.messages:
                if msg.text:
                    text = msg.text
                    break

        needs_input = response_needs_input(text)
        print(f"  [FieldExec] Done. Needs input: {needs_input}")
        await ctx.send_message(FieldResponse(text=text, needs_input=needs_input))


# ── OpsRouter — orchestration logic ──────────────────────────

class OpsRouter(Executor):
    """Central router that controls the full conversation flow.

    Handles:
    - Initial message classification and dispatch
    - Collecting responses from specialists
    - HITL interaction with operator via request_info
    - Multi-turn state tracking
    """

    def __init__(self):
        super().__init__(id="ops_router")
        self.conversation: list[Message] = []
        self.active_agent: str | None = None  # "case" | "field" | None
        self.case_id: str | None = None
        self.pending_outputs: list[str] = []  # Accumulate outputs before showing to operator

    def _build_messages(self, extra_text: str | None = None) -> list[Message]:
        """Build message list for an agent call, including full conversation."""
        msgs = list(self.conversation)
        if extra_text:
            msgs.append(Message("user", text=extra_text))
        return msgs

    @handler
    async def on_initial(
        self, text: str, ctx: WorkflowContext[CaseRequest | FieldRequest]
    ) -> None:
        """Handle the initial operator message."""
        self.conversation.append(Message("user", text=text))
        intent = classify_intent(text)
        print(f"  [Router] Initial message. Intent: {intent}")

        if intent in ("new_report", "both"):
            # New situation → CaseManager first
            await ctx.send_message(
                CaseRequest(messages=self._build_messages(), task_hint="create")
            )
        elif intent == "case":
            await ctx.send_message(
                CaseRequest(messages=self._build_messages(), task_hint="manage")
            )
        elif intent == "field":
            await ctx.send_message(
                FieldRequest(messages=self._build_messages())
            )
        else:
            # Unknown — try field as default
            await ctx.send_message(
                FieldRequest(messages=self._build_messages())
            )

    @handler
    async def on_case_response(
        self, response: CaseResponse, ctx: WorkflowContext[FieldRequest, str]
    ) -> None:
        """Handle response from CaseManager."""
        print(f"  [Router] CaseManager responded. Case: {response.case_id or 'N/A'}")
        self.conversation.append(Message("assistant", text=response.text))

        if response.case_id:
            self.case_id = response.case_id

        self.pending_outputs.append(response.text)

        # After case creation on a new report → dispatch to FieldSpecialist
        last_user = ""
        for msg in reversed(self.conversation):
            if msg.role == "user":
                last_user = msg.text or ""
                break

        intent = classify_intent(last_user)
        if intent in ("new_report", "both"):
            # Also need field assessment
            print(f"  [Router] Also dispatching to FieldSpecialist...")
            await ctx.send_message(
                FieldRequest(messages=self._build_messages())
            )
        else:
            # Case-only request — show result to operator
            combined = "\n".join(self.pending_outputs)
            self.pending_outputs.clear()
            await ctx.request_info(
                request_data=OperatorPrompt(prompt=combined),
                response_type=str,
            )

    @handler
    async def on_field_response(
        self, response: FieldResponse, ctx: WorkflowContext[CaseRequest]
    ) -> None:
        """Handle response from FieldSpecialist."""
        print(f"  [Router] FieldSpecialist responded. Needs input: {response.needs_input}")
        self.conversation.append(Message("assistant", text=response.text))
        self.pending_outputs.append(response.text)

        if response.needs_input:
            # Agent needs more info from operator
            self.active_agent = "field"
            combined = "\n".join(self.pending_outputs)
            self.pending_outputs.clear()
            await ctx.request_info(
                request_data=OperatorPrompt(prompt=combined),
                response_type=str,
            )
        else:
            # Field assessment complete → update case if we have one
            if self.case_id:
                update_text = (
                    f"Update case {self.case_id} with these findings:\n"
                    f"{response.text}"
                )
                self.conversation.append(Message("user", text=update_text))
                await ctx.send_message(
                    CaseRequest(
                        messages=self._build_messages(),
                        task_hint="update",
                    )
                )
            else:
                # No case — just show to operator
                self.active_agent = None
                combined = "\n".join(self.pending_outputs)
                self.pending_outputs.clear()
                await ctx.request_info(
                    request_data=OperatorPrompt(prompt=combined),
                    response_type=str,
                )

    @response_handler
    async def on_operator_response(
        self,
        original_request: OperatorPrompt,
        feedback: str,
        ctx: WorkflowContext[CaseRequest | FieldRequest],
    ) -> None:
        """Handle operator's response to a prompt."""
        self.conversation.append(Message("user", text=feedback))
        print(f"  [Router] Operator responded. Active agent: {self.active_agent}")

        if self.active_agent == "field":
            # Continue with FieldSpecialist (e.g., operator gave coordinates)
            self.active_agent = None
            await ctx.send_message(
                FieldRequest(messages=self._build_messages())
            )
        elif self.active_agent == "case":
            self.active_agent = None
            await ctx.send_message(
                CaseRequest(messages=self._build_messages(), task_hint="manage")
            )
        else:
            # Re-classify the new message
            intent = classify_intent(feedback)
            print(f"  [Router] Re-classified intent: {intent}")

            if intent in ("case", "both"):
                await ctx.send_message(
                    CaseRequest(messages=self._build_messages(), task_hint="manage")
                )
            elif intent == "field":
                await ctx.send_message(
                    FieldRequest(messages=self._build_messages())
                )
            elif intent == "new_report":
                await ctx.send_message(
                    CaseRequest(messages=self._build_messages(), task_hint="create")
                )
            else:
                # Default: field
                await ctx.send_message(
                    FieldRequest(messages=self._build_messages())
                )


# ── Build workflow ────────────────────────────────────────────

def build_workflow(client):
    """Build the WorkflowBuilder graph."""
    case_manager = create_case_manager(client)
    field_specialist = create_field_specialist(client)

    router = OpsRouter()
    case_exec = CaseExec(case_manager)
    field_exec = FieldExec(field_specialist)

    workflow = (
        WorkflowBuilder(start_executor=router)
        # Router dispatches to specialists
        .add_edge(router, case_exec)
        .add_edge(router, field_exec)
        # Specialists report back to router
        .add_edge(case_exec, router)
        .add_edge(field_exec, router)
    ).build()

    return workflow


# ── Event processing ──────────────────────────────────────────

async def process_event_stream(stream) -> dict[str, str] | None:
    """Process events from workflow stream. Return pending HITL responses or None."""
    requests: list[tuple[str, OperatorPrompt]] = []

    async for event in stream:
        if event.type == "request_info" and isinstance(event.data, OperatorPrompt):
            requests.append((event.request_id, event.data))
        elif event.type == "output":
            data = event.data
            if isinstance(data, AgentResponseUpdate):
                if data.text:
                    print(data.text, end="", flush=True)
            elif isinstance(data, str):
                print(f"\n  [Output]: {data}")

    # Show accumulated output and get operator input
    if requests:
        responses: dict[str, str] = {}
        for request_id, request in requests:
            # Display the agent's output
            print_agent_message("System", request.prompt)
            print(f"\n{SEP}")
            print("\n  OPERATOR (you): ", end="", flush=True)
            answer = input().strip()
            if answer == "/quit":
                return None
            responses[request_id] = answer
        return responses

    return None


# ── Main loop ─────────────────────────────────────────────────

async def main():
    print_config(
        "PROTOTYPE 08 — WorkflowBuilder + Custom Executor",
        "WorkflowBuilder + OpsRouter + typed messages | Routing: hybrid regex + state",
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

    # First run
    stream = workflow.run(initial, stream=True)
    pending_responses = await process_event_stream(stream)

    # HITL loop
    while pending_responses is not None:
        print(f"\n  Processing...\n")
        stream = workflow.run(stream=True, responses=pending_responses)
        pending_responses = await process_event_stream(stream)

    print(f"\n{SEP}")
    print("  Done.")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
