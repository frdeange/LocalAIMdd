# Agent Design Guide

## Overview

This guide provides best practices for designing effective agents within the
Travel Planner orchestration. Good agent design is critical when using local
Small Language Models (SLMs) which have more limited capacity than cloud LLMs.

## Prompt Engineering for Local SLMs

### Keep Instructions Concise

Local models via Ollama (phi4-mini, qwen2.5, llama3.2) have shorter context
windows and less reasoning capacity than GPT-4. Write clear, structured prompts:

**Good:**
```
You are a travel researcher. Given a destination, provide:
1. Key attractions
2. Local culture
3. Transportation
Output bullet points only.
```

**Bad:**
```
You are a world-class travel expert with 20 years of experience who has visited
every country and can provide incredibly detailed, nuanced, and comprehensive
analyses of any travel destination including its history, geography, demographics,
political landscape, economic conditions...
```

### Use Numbered Lists

SLMs respond well to numbered instructions. They follow structured prompts
more reliably than free-form ones.

### Explicit Output Format

Always specify the expected output format:
- "Use bullet points"
- "Output ONLY the analysis — no greetings"
- "Respond in 3-5 sentences"

### Tool Usage Instructions

For tool-equipped agents, be explicit about when and how to use tools:

```
You MUST use the get_weather tool to fetch weather data.
Do NOT guess or make up weather information.
Call the tool first, then summarize the result.
```

## Agent Design Patterns

### Pattern 1: LLM-Only Agent (Researcher, Planner)

```python
def create_my_agent(client):
    return client.as_agent(
        name="MyAgent",
        instructions="Clear, concise instructions...",
    )
```

- No tools — relies on model knowledge
- Best for synthesis, summarization, and creative tasks
- Keep instructions under 200 words

### Pattern 2: Tool-Equipped Agent (WeatherAnalyst)

```python
def create_my_agent(client, mcp_url):
    mcp_tool = MCPStreamableHTTPTool(
        name="tools",
        url=mcp_url,
    )
    agent = client.as_agent(
        name="MyAgent",
        instructions="Use the tools to get data, then analyze...",
        tools=[mcp_tool],
    )
    return agent, mcp_tool
```

- Uses MCP tools for external data
- Instructions MUST tell the agent to call tools
- Returns tuple: (agent, mcp_tool) for lifecycle management

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Module file | `snake_case.py` | `weather_analyst.py` |
| Factory function | `create_<name>_agent()` | `create_weather_analyst_agent()` |
| Agent name | PascalCase | `"WeatherAnalyst"` |
| MCP tool name | descriptive_snake | `"travel_tools"` |

## Common Pitfalls

### 1. Too Many Tools per Agent

SLMs struggle with more than 3-5 tools. If an agent needs many tools,
split it into multiple specialized agents.

### 2. Vague Instructions

"Be helpful and informative" tells the model nothing. Be specific about
what data to produce and in what format.

### 3. Tool Hallucination

SLMs may "imagine" calling a tool. Always include:
```
ALWAYS call the appropriate tool first — do NOT answer from memory.
```

### 4. Context Window Overflow

In a sequential workflow, each agent sees ALL previous messages.
With 3+ agents and a verbose model, the context can grow quickly.
Keep agent responses concise to leave room for downstream agents.

### 5. Forgetting Tool Lifecycle

`MCPStreamableHTTPTool` is a connection-based resource. Always manage it
with `async with mcp_tool:` or call `await mcp_tool.connect()` explicitly.

## Testing Agents

While you can't unit-test LLM responses (they're non-deterministic), you CAN test:

1. **Factory functions exist and are callable** — `test_architecture.py`
2. **Source code patterns** — Uses `as_agent()`, correct tool imports
3. **Instructions contain required keywords** — Verify prompt structure
4. **Integration** — Full workflow with real model (manual/CI)

## Model Selection

Available FoundryLocal models with tool support:

| Model | Size | Tool Calling | Notes |
|-------|------|-------------|-------|
| `Phi-4-mini-instruct-cuda-gpu:5` | ~5 GB | ✅ | Recommended default |
| `qwen2.5-7b-instruct-cuda-gpu:4` | ~4 GB | ✅ | Good alternative |

Set the model via `FOUNDRY_LOCAL_MODEL_ID` in `.env`. Note that FoundryLocal
serves one model at a time — all agents share the same model.
