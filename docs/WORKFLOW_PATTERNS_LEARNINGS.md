# MAF Workflow Patterns — Learnings & Evaluation

> **Date:** 2026-03-04
> **Status:** Active research — prototyping phase

---

## Context

During the implementation of the BMS Operations PoC, we evaluated
multiple MAF (Microsoft Agent Framework) orchestration patterns for
routing operator messages to specialist agents. This document captures
our findings, what works, what doesn't, and why.

## Architecture Goal

```
Field Operator (voice/text)
      │
      ▼
┌──────────────────────────────────────────────────┐
│  Orchestration Layer                              │
│  Decides which specialist(s) should act           │
│  Manages conversation state across turns          │
└──────┬──────────────┬────────────────────────────┘
       │              │
       ▼              ▼
┌─────────────┐  ┌──────────────┐
│ CaseManager │  │FieldSpecialis│
│ (MCP BMS)   │  │ (MCP Camera  │
│             │  │  + Weather)  │
└─────────────┘  └──────────────┘
```

The operator speaks naturally. The system should:
1. Create a BMS case automatically when a new situation is reported
2. Route to the appropriate specialist based on need
3. Let specialists ask for missing information (e.g., coordinates)
4. Relay specialist questions/responses back to the operator
5. Support multi-turn conversations

---

## Patterns Evaluated

### 1. HandoffBuilder (L3 — Prototype 04)

**How it works:** Agents route to each other via `transfer_to_*` tool
calls. The Orchestrator decides who to transfer to next.

**Prototype:** `prototypes/04_multiturn_handoff.py`

#### Results by model:

| Model | Tool Call Reliability | Behaviour |
|---|---|---|
| qwen2.5:7b | ❌ Inconsistent | Sometimes generates `transfer_to_FieldSpecialist` as TEXT instead of tool call. Loops forever in API mode. |
| qwen2.5:14b | ✅ Reliable | Handoff works. Asks for coordinates. MCP tools execute correctly. Best overall result. |
| llama3.1:8b | ✅ Reliable | Always executes tool call. But too proactive — invents coordinates instead of asking. |
| phi4-mini | ❌ Broken | Generates raw JSON tool definition as text. Not usable. |
| qwen3.5:4b | ❌ Does not hand off | Orchestrator keeps the conversation, never routes to specialists. |

#### Key findings:

- **HandoffBuilder works well with qwen2.5:14b** — reliable tool calling,
  good Spanish, asks for missing info, synthesizes results
- **Smaller models (7b, 4b) are unreliable** — tool calling is inconsistent
- **The HITL pattern is correct** — operator's messages ARE the HITL responses.
  Each push-to-talk = one HITL turn.
- **Instructions should NOT mention tool names** — when instructions include
  `transfer_to_FieldSpecialist` explicitly, small models generate it as text
  instead of executing it
- **Simple instructions work better** — follow the official MAF sample style:
  describe roles, not function names

#### Agent instruction patterns that work:

```python
# GOOD — simple, no function names
"You are a military operations coordinator. "
"Route reconnaissance tasks to the field specialist. "
"Route case management tasks to the case manager."

# BAD — mentions function names → model generates them as text
"You have TWO transfer tools:\n"
"• transfer_to_CaseManager — for creating cases\n"
"• transfer_to_FieldSpecialist — for reconnaissance"
```

#### HandoffBuilder architecture issue:

The HandoffBuilder HITL at L3 means the Orchestrator decides routing
AND the operator provides input in the same loop. When the Orchestrator
makes a handoff, the specialist responds, and the response goes back
through HITL → the operator sees the specialist's answer and can respond.

This creates an indirect flow:
```
Operator → Orchestrator (HITL) → Specialist → Orchestrator (HITL) → Operator
```

The operator never talks directly to the specialist — the Orchestrator
always mediates. This is good for control but adds latency (2 LLM calls
per round: routing + specialist).

#### Performance issue:

qwen2.5:14b (9GB) doesn't fit in 6GB GPU → runs on CPU → 2-5 minutes
per response. Acceptable for PoC validation but not for real-time voice.

---

### 2. GroupChatBuilder with selection_func (Prototype 05)

**How it works:** A selection function (can be LLM-based) decides which
agent speaks next. All agents see the full conversation.

**Prototype:** `prototypes/05_groupchat.py`

#### Results:

- **Selection function works** — successfully routes to CaseManager first,
  then FieldSpecialist
- **CaseManager creates real cases via MCP BMS** ✅
- **`with_request_info()` creates wrong HITL pattern** — it loops the
  operator's response back to the SAME agent instead of re-running the
  selector. Result: CaseManager keeps answering everything.
- **Without `with_request_info()`**, the workflow runs all rounds
  autonomously (no operator interaction between rounds)
- **`orchestrator_agent` mode is incompatible with Ollama** — requires
  structured JSON output (`format=AgentOrchestrationOutput`) which
  Ollama doesn't support

#### Key finding:

GroupChatBuilder's HITL (`with_request_info`) is designed for
**approval workflows** (agent responds → human approves/revises →
agent continues), NOT for **multi-turn conversations** where
different agents take turns.

For our use case (operator talks, system routes to different agents),
GroupChat would need a **stateful conversation loop** where each
operator message triggers a new GroupChat run with conversation history.

#### GroupChat architecture issue:

```
Turn 1: Operator → [Selector → CaseManager] → agent responds
Turn 2: Operator → [Selector → FieldSpecialist] → agent responds
```

But each turn is a separate workflow run. The conversation history
must be passed as context. This loses the benefits of MAF managing
the conversation state.

---

### 3. Direct Agent Calls (bypass approach — tried in production)

**How it works:** Regex keyword routing in `bms_api/workflow.py`
decides which agent to call directly. No HandoffBuilder, no GroupChat.

#### Results:

- **Regex routing is 100% reliable** — no LLM needed for routing
- **Loses all MAF intelligence** — can't handle multi-part requests
  ("check the vehicle AND create a case")
- **Agents work in isolation** — no conversation context between agents
- **FieldSpecialist without coordinates invents them** (llama3.1:8b)
  or doesn't ask (depends on model)

#### Verdict: not suitable for the PoC goals

---

## Performance by Model

| Model | Size | GPU? | Response Time | Tool Calling | Spanish | Verdict |
|---|---|---|---|---|---|---|
| qwen2.5:7b | 4.7GB | ✅ GPU | ~30-60s | ❌ Inconsistent | ✅ Good | Not reliable enough |
| qwen2.5:14b | 9GB | ❌ CPU | ~2-5min | ✅ Reliable | ✅ Good | **Best quality, too slow** |
| llama3.1:8b | 4.9GB | ✅ GPU | ~30-60s | ✅ Reliable | ✅ OK | Too proactive (invents data) |
| phi4-mini | 2.5GB | ✅ GPU | ~15-30s | ❌ Broken | ❌ English-only | Not usable |
| qwen3.5:4b | 2.5GB | ✅ GPU | ~15-30s | ❌ No handoff | ✅ OK | Not capable enough |

---

## Recommended Architecture

Based on all prototyping:

### For the PoC (limited hardware):

**HandoffBuilder + qwen2.5:14b** is the best combination:
- Reliable tool calling (handoffs work)
- Good Spanish
- Asks for missing information
- Synthesizes MCP data well
- Main drawback: slow on CPU (needs bigger GPU for production)

### For production:

**Either:**
1. **HandoffBuilder + larger GPU** (RTX 3090 24GB or A100) → qwen2.5:14b
   runs on GPU → fast responses
2. **GroupChatBuilder with custom orchestrator** → once MAF supports
   Ollama structured output, `orchestrator_agent` mode would be ideal
3. **Cloud LLM** (Azure OpenAI) → reliable tool calling, fast, but
   requires internet (not offline)

---

## Open Questions

1. Can we quantize qwen2.5:14b to fit in 6GB GPU?
   (Default is already Q4_K_M — 9GB. Would need Q2 or Q3 → quality loss)

2. Would GGUF partial offloading help?
   (Some layers GPU, rest CPU — might be 2-3x faster than pure CPU)

3. Is there a better model in the 7-8B range for tool calling?
   (We haven't tried Mistral 7B or Gemma2 9B)

4. Can we make GroupChat's `with_request_info()` work for multi-turn
   by using the `agents` filter parameter?

5. Should we consider a hybrid: Orchestrator as simple keyword router
   (fast, reliable) + specialists as full LLM agents with MCP tools?

---

## Files Reference

| File | Pattern | Status |
|---|---|---|
| `prototypes/04_multiturn_handoff.py` | HandoffBuilder interactive | Working with qwen2.5:14b |
| `prototypes/05_groupchat.py` | GroupChat with selection_func | Partially working |
| `src/runner.py` | HandoffBuilder CLI (production) | Working |
| `bms_api/workflow.py` | Direct agent calls (bypass) | Deployed but not ideal |
