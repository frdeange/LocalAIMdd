"""MeteoAgent — Meteorological analyst (MCP-connected)."""

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.ollama import OllamaChatClient

from src.config import MCP_WEATHER_URL

METEO_INSTRUCTIONS = """\
You are a meteorological analyst in a battlefield management system.

You have access to a weather station via the `get_weather_report` tool.

When given coordinates or a target location:
1. Call the `get_weather_report` tool with the coordinates.
2. Present the tool's results as a concise WEATHER BRIEF with bullet points:
   - Current conditions: temperature, cloud cover, wind, visibility, humidity
   - Operational impact: surveillance quality, vehicle mobility, helo ops
   - 6-hour forecast with risk assessment
3. Do NOT fabricate data — report exactly what the tool returns.
   Use precise units (°C, km/h, km visibility, %% humidity).
"""


def create_meteo_agent(client: OllamaChatClient) -> Agent:
    """Create the MeteoAgent with MCP Weather tool."""
    weather_mcp = MCPStreamableHTTPTool(
        name="weather_mcp",
        url=MCP_WEATHER_URL,
        description="Meteorological weather station",
    )
    return client.as_agent(
        name="MeteoAgent",
        instructions=METEO_INSTRUCTIONS,
        tools=[weather_mcp],
    )
