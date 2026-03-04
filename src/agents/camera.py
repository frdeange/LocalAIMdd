"""CameraAgent — Surveillance camera operator (MCP-connected)."""

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.ollama import OllamaChatClient

from src.config import MCP_CAMERA_URL

CAMERA_INSTRUCTIONS = """\
You are a surveillance camera operator in a battlefield management system.

IMPORTANT: Always respond in the SAME LANGUAGE as the operator's message.
Do NOT use markdown formatting (no **, #, -, bullet points). Use plain text
only — your responses will be read aloud via text-to-speech.

You have access to a camera system via the `get_camera_feed` tool.

When given coordinates or a target location:
1. Call the `get_camera_feed` tool with the coordinates to capture the scene.
2. Present the tool's results as a concise CAMERA REPORT with bullet points:
   - Target description (vehicles, personnel, structures)
   - Environment and terrain
   - Image quality and visibility conditions
   - Tactical notes
3. Do NOT fabricate observations — report exactly what the tool returns.
"""


def create_camera_agent(client: OllamaChatClient) -> Agent:
    """Create the CameraAgent with MCP Camera tool."""
    camera_mcp = MCPStreamableHTTPTool(
        name="camera_mcp",
        url=MCP_CAMERA_URL,
        description="Surveillance camera system",
    )
    return client.as_agent(
        name="CameraAgent",
        instructions=CAMERA_INSTRUCTIONS,
        tools=[camera_mcp],
    )
