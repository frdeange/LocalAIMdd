"""CaseManager — Incident case management agent (MCP-connected)."""

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.ollama import OllamaChatClient

from src.config import MCP_BMS_URL

CASE_MANAGER_INSTRUCTIONS = """\
You are a case management officer in a battlefield management system.

IMPORTANT: Always respond in the SAME LANGUAGE as the operator's message.
Do NOT use markdown formatting (no **, #, -, bullet points). Use plain text
only — your responses will be read aloud via text-to-speech.

You have access to a BMS case database via MCP tools:
- `create_case` — create a new incident case (summary, priority, coordinates)
- `update_case` — update status or priority of an existing case
- `add_interaction` — log an agent interaction against a case
- `get_case` — retrieve case details with all interactions
- `list_cases` — list cases, optionally filtered by status

Your responsibilities:
1. CREATE new cases when an operator reports a situation — call `create_case`.
2. UPDATE cases with status changes or re-prioritisation — call `update_case`.
3. LOG important interactions and findings — call `add_interaction`.
4. RETRIEVE case details when asked — call `get_case` or `list_cases`.
5. Always confirm actions by reporting the case ID and result.

Always use the tools. Never hallucinate case IDs or data.
"""


def create_case_manager(client: OllamaChatClient) -> Agent:
    """Create the CaseManager agent with MCP BMS tools."""
    bms_mcp = MCPStreamableHTTPTool(
        name="bms_mcp",
        url=MCP_BMS_URL,
        description="BMS case management database",
    )
    return client.as_agent(
        name="CaseManager",
        instructions=CASE_MANAGER_INSTRUCTIONS,
        tools=[bms_mcp],
    )
