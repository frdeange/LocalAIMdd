# Creating Workflows

## Overview

Workflows orchestrate multiple agents into coordinated execution patterns.
This project uses MAF's **SequentialBuilder** for ordered, pipeline-style workflows.

## Available Orchestration Patterns

MAF provides several orchestration builders:

| Pattern | Builder | Use Case |
|---------|---------|----------|
| Sequential | `SequentialBuilder` | Pipeline: A → B → C |
| Concurrent | `ConcurrentBuilder` | Fan-out/fan-in: A + B + C → merge |
| Handoff | `HandoffBuilder` | Agent-to-agent delegation |
| GroupChat | `GroupChatBuilder` | Multi-turn conversation |
| Magentic | `MagenticBuilder` | Dynamic task routing |

This PoC uses **Sequential** — the simplest and most predictable pattern.

## Creating a New Sequential Workflow

### 1. Define the Workflow Builder Function

Create a new file in `src/workflows/`, e.g. `src/workflows/content_pipeline.py`:

```python
"""
Content Pipeline Workflow
=========================
Sequential: Researcher → Writer → Editor
"""

from agent_framework.orchestrations import SequentialBuilder


def build_content_pipeline(client: object) -> object:
    """Build a content creation pipeline workflow.

    Args:
        client: An OllamaChatClient for creating agents.

    Returns:
        A Workflow instance ready for execution.
    """
    researcher = client.as_agent(
        name="Researcher",
        instructions="Research the topic and provide facts...",
    )

    writer = client.as_agent(
        name="Writer",
        instructions="Write engaging content based on the research...",
    )

    editor = client.as_agent(
        name="Editor",
        instructions="Review and polish the content...",
    )

    workflow = SequentialBuilder(
        participants=[researcher, writer, editor],
    ).build()

    return workflow
```

### 2. Register in the Package

Update `src/workflows/__init__.py`:

```python
from .content_pipeline import build_content_pipeline

__all__ = [
    "build_travel_planner_workflow",
    "build_content_pipeline",
]
```

### 3. Run the Workflow

```python
import asyncio
from agent_framework import Message

async def main():
    workflow = build_content_pipeline(client)

    # Non-streaming execution
    result = await workflow.run("Write about electric vehicles")
    outputs = result.get_outputs()

    # Streaming execution
    async for event in workflow.run("Write about AI agents", stream=True):
        if event.type == "output":
            messages = event.data  # list[Message]
            for msg in messages:
                print(f"{msg.author_name}: {msg.text}")
```

## Key Concepts

### Conversation Context

In a `SequentialBuilder` workflow, each agent receives the **full conversation history**
from all previous agents as a `list[Message]`. This means:

- Agent 1 sees: `[user_query]`
- Agent 2 sees: `[user_query, agent_1_response]`
- Agent 3 sees: `[user_query, agent_1_response, agent_2_response]`

### MCP Tool Lifecycle

If any agent uses `MCPStreamableHTTPTool`, the tool must be connected before workflow
execution and disconnected after:

```python
workflow, mcp_tool = build_travel_planner_workflow(client, mcp_url)

async with mcp_tool:  # Connect to MCP server
    async for event in workflow.run(query, stream=True):
        ...
# MCP connection automatically closed here
```

### Workflow Events

When streaming, the workflow emits events:

| Event Type | Description |
|-----------|-------------|
| `status` | Workflow state changes (running, idle) |
| `executor_invoked` | An agent/executor started processing |
| `executor_completed` | An agent/executor finished |
| `output` | Final workflow output (list[Message]) |

### Wrapping as an Agent

Any workflow can be wrapped as a single agent using `.as_agent()`:

```python
workflow = SequentialBuilder(participants=[a, b, c]).build()
agent = workflow.as_agent(name="PipelineAgent")

# Now use it as a regular agent
result = await agent.run("some input")
```

This enables **workflow composition** — a workflow can participate in another workflow.

## Testing Workflows

Add pattern-validation tests in `tests/test_workflow_patterns.py`:

```python
def test_my_workflow_uses_sequential_builder():
    import inspect
    source = inspect.getsource(build_content_pipeline)
    assert "SequentialBuilder" in source
    assert "participants=" in source
```
