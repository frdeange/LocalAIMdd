"""
Workflow Service
================
Runs the MAF SequentialBuilder pipeline and yields SSE events.
Translates MAF streaming events into the SSE event protocol.

Key design decisions:
- Uses ``event.executor_id`` to identify agents (reliable; replaces the
  fragile counter-based approach that broke with tool-calling rounds and
  internal adapter executors like ``input-conversation`` / ``end``).
- Buffers output per agent and emits ``agent_completed`` only once per agent
  (with the longest/best output).  Extra executor rounds for the same agent
  (e.g. WeatherAnalyst tool-calling) are silently merged into its buffer.
- Properly extracts text from MAF event.data which contains
  ``AgentExecutorResponse`` and ``AgentResponse``/``AgentResponseUpdate``
  objects — NOT plain ``Message`` objects.
- Strips ``=== PREVIOUS CONVERSATION CONTEXT ===`` markers.
- The final ``output`` event (from the SequentialBuilder's "end" executor)
  carries ``list[Message]`` — the full conversation — from which we extract
  the last assistant text.  If an agent (especially Planner) produced empty
  output, the workflow final output is used as the Planner's content.
"""

import json
import logging
import re
from typing import AsyncGenerator

from src.telemetry import trace_workflow
from src.workflows.travel_planner import build_travel_planner_workflow

logger = logging.getLogger(__name__)

# Agent names in execution order (must match SequentialBuilder participant order)
AGENT_SEQUENCE = ["Researcher", "WeatherAnalyst", "Planner"]
_AGENT_SET = frozenset(AGENT_SEQUENCE)

# Regex to strip echoed conversation-context markers from agent output
_CONTEXT_PREFIX_RE = re.compile(
    r"===\s*PREVIOUS CONVERSATION CONTEXT\s*===.*?===\s*END OF CONTEXT\s*===\s*",
    re.DOTALL,
)


def _sse_line(event: str, data: dict) -> str:
    """Format a single SSE event line."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _extract_text(data) -> str:
    """Extract the best text from MAF event data.

    MAF ``executor_completed`` event.data is a list of:
        - ``AgentExecutorResponse`` (.agent_response.text → full response)
        - ``AgentResponse`` (.text → full text, .messages → Message list)
        - ``AgentResponseUpdate`` (.text → partial chunk)

    The workflow ``output`` event.data is ``list[Message]``, where each
    Message has ``.role`` and ``.text``.

    Strategy: recurse into lists, try the richest accessor first
    (AgentExecutorResponse > AgentResponse > Message), keep longest.
    """
    if data is None:
        return ""

    if isinstance(data, str):
        return data

    # ── AgentExecutorResponse → .agent_response.text (full response) ──
    agent_resp = getattr(data, "agent_response", None)
    if agent_resp is not None:
        text = getattr(agent_resp, "text", None)
        if isinstance(text, str) and text.strip():
            return text

    # ── AgentResponse / AgentResponseUpdate / Message → .text ──
    text = getattr(data, "text", None)
    if isinstance(text, str) and text.strip():
        # For Message objects, only accept assistant role
        role = getattr(data, "role", None)
        if role is None or role == "assistant":
            return text

    # ── list / tuple → recurse, keep longest ──
    if isinstance(data, (list, tuple)):
        best = ""
        for item in data:
            t = _extract_text(item)
            if len(t) > len(best):
                best = t
        return best

    return ""


def _extract_last_assistant(messages) -> str:
    """Extract last assistant message text from a list[Message] conversation."""
    if not isinstance(messages, (list, tuple)):
        return _extract_text(messages)
    for msg in reversed(messages):
        role = getattr(msg, "role", None)
        text = getattr(msg, "text", None)
        if role == "assistant" and isinstance(text, str) and text.strip():
            return text
    return ""


def _clean_output(text: str) -> str:
    """Strip context-prefix markers and filter trivial outputs.

    Returns an empty string for outputs that are meaningless (single char,
    bare punctuation, etc.) so callers can decide whether to show them.
    """
    if not text:
        return ""
    # Remove echoed context-prefix block
    text = _CONTEXT_PREFIX_RE.sub("", text)
    text = text.strip()
    # Filter trivially short / punctuation-only outputs
    if len(text) <= 1 or text in ("-", ".", "...", "—", "–"):
        return ""
    return text


def _agent_step(name: str) -> int:
    """Return the 1-based step number for an agent name."""
    try:
        return AGENT_SEQUENCE.index(name) + 1
    except ValueError:
        return len(AGENT_SEQUENCE)


async def run_workflow_sse(
    client: object,
    mcp_server_url: str,
    query: str,
) -> AsyncGenerator[str, None]:
    """Run the travel planner workflow and yield SSE-formatted events.

    This is the core bridge between MAF's SequentialBuilder streaming events
    and the SSE protocol consumed by the frontend.

    The function uses ``event.executor_id`` to identify which agent each
    MAF event belongs to, buffers output per agent, and emits exactly one
    ``agent_started`` + one ``agent_completed`` SSE event per logical agent.
    Extra executor rounds (tool-calling, internal adapters) are silently
    handled.

    Args:
        client: OllamaChatClient instance.
        mcp_server_url: URL of the MCP server.
        query: The user's travel planning request (with optional context prefix).

    Yields:
        SSE-formatted strings (event + data lines).
    """
    try:
        workflow, mcp_tool = build_travel_planner_workflow(
            client=client,
            mcp_server_url=mcp_server_url,
        )

        yield _sse_line("workflow_started", {"workflow": "travel_planner"})

        with trace_workflow("travel_planner", query):
            async with mcp_tool:
                logger.info("MCP tool connected to %s", mcp_server_url)

                # ── state tracking ────────────────────────────────
                started_agents: set[str] = set()
                completed_agents: set[str] = set()
                agent_buffers: dict[str, str] = {}   # agent → best cleaned output
                current_agent: str | None = None
                last_meaningful_output = ""
                got_final_output = False

                async for event in workflow.run(query, stream=True):
                    etype = event.type
                    eid = getattr(event, "executor_id", None) or ""

                    logger.debug(
                        "MAF event: type=%s, executor_id=%s, data_type=%s",
                        etype,
                        eid,
                        type(getattr(event, "data", None)).__name__,
                    )

                    # ── executor_invoked (agent) ──────────────────
                    if etype == "executor_invoked" and eid in _AGENT_SET:
                        # Transitioning to a different agent → flush previous
                        if (
                            current_agent
                            and current_agent != eid
                            and current_agent not in completed_agents
                        ):
                            completed_agents.add(current_agent)
                            buf = agent_buffers.get(current_agent, "")
                            if buf:
                                last_meaningful_output = buf
                            step = _agent_step(current_agent)
                            yield _sse_line("agent_completed", {
                                "agent": current_agent,
                                "step": step,
                                "output": buf,
                            })
                            logger.info(
                                "Agent completed: %s (step %d, output_len=%d)",
                                current_agent, step, len(buf),
                            )

                        current_agent = eid

                        # Emit agent_started only once per agent
                        if eid not in started_agents:
                            started_agents.add(eid)
                            agent_buffers.setdefault(eid, "")
                            step = _agent_step(eid)
                            yield _sse_line("agent_started", {
                                "agent": eid,
                                "step": step,
                            })
                            logger.info("Agent started: %s (step %d)", eid, step)

                    # ── executor_completed (agent) ────────────────
                    elif etype == "executor_completed" and eid in _AGENT_SET:
                        raw = _extract_text(getattr(event, "data", None))
                        output = _clean_output(raw)

                        # Keep the longest (best) output for this agent
                        if len(output) > len(agent_buffers.get(eid, "")):
                            agent_buffers[eid] = output

                        logger.debug(
                            "Executor completed: %s (raw_len=%d, clean_len=%d, best=%d)",
                            eid,
                            len(raw),
                            len(output),
                            len(agent_buffers.get(eid, "")),
                        )

                    # ── workflow output (from "end" executor) ─────
                    elif etype == "output":
                        got_final_output = True

                        # Extract final text from full conversation
                        final_data = getattr(event, "data", None)
                        final_text = _clean_output(_extract_last_assistant(final_data))
                        if not final_text:
                            final_text = _clean_output(_extract_text(final_data))

                        # Flush all agents in pipeline order
                        for name in AGENT_SEQUENCE:
                            if name not in started_agents:
                                continue
                            if name not in completed_agents:
                                completed_agents.add(name)
                                buf = agent_buffers.get(name, "")

                                # If this is the last agent and it has no
                                # output, use the workflow final text instead
                                if not buf and name == AGENT_SEQUENCE[-1]:
                                    buf = final_text or last_meaningful_output

                                if buf:
                                    last_meaningful_output = buf

                                step = _agent_step(name)
                                yield _sse_line("agent_completed", {
                                    "agent": name,
                                    "step": step,
                                    "output": buf,
                                })
                                logger.info(
                                    "Agent completed: %s (step %d, output_len=%d)",
                                    name, step, len(buf),
                                )

                        # Workflow-level final output
                        wf_final = final_text or last_meaningful_output
                        yield _sse_line("workflow_completed", {
                            "final_output": wf_final,
                        })
                        logger.info(
                            "Workflow completed (output_len=%d)", len(wf_final),
                        )

                # Safety: if the loop ended without an 'output' event
                if not got_final_output:
                    logger.warning(
                        "No output event received — flushing remaining state"
                    )
                    for name in AGENT_SEQUENCE:
                        if name in started_agents and name not in completed_agents:
                            completed_agents.add(name)
                            buf = agent_buffers.get(name, "")
                            if buf:
                                last_meaningful_output = buf
                            step = _agent_step(name)
                            yield _sse_line("agent_completed", {
                                "agent": name,
                                "step": step,
                                "output": buf,
                            })
                    yield _sse_line("workflow_completed", {
                        "final_output": last_meaningful_output,
                    })

    except Exception as e:
        logger.exception("Workflow execution failed: %s", e)
        yield _sse_line("error", {"message": str(e)})
