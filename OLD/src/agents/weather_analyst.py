"""
Weather Analyst Agent
=====================
Analyzes weather conditions for travel destinations using MCP tools.
Connects to the FastMCP server to fetch real-time weather data.

This agent is the second step in the Travel Planner sequential workflow.
"""

from agent_framework import Agent, MCPStreamableHTTPTool


def create_weather_analyst_agent(client: object, mcp_server_url: str) -> tuple[Agent, MCPStreamableHTTPTool]:
    """Create the Weather Analyst agent with MCP tool access.

    Args:
        client: A FoundryLocalClient (or any client implementing as_agent).
        mcp_server_url: URL of the MCP server (e.g. "http://localhost:8090/mcp").

    Returns:
        A tuple of (Agent, MCPStreamableHTTPTool) — the tool must be used as a
        context manager to maintain the MCP connection.
    """
    mcp_tool = MCPStreamableHTTPTool(
        name="travel_tools",
        url=mcp_server_url,
        description="Travel tools: weather, time, restaurants",
    )

    agent = client.as_agent(  # type: ignore[union-attr]
        name="WeatherAnalyst",
        instructions=(
            "You are a weather and travel conditions analyst. Based on the research brief "
            "from the previous agent and the destination mentioned, you MUST:\n"
            "1. Use the get_weather tool to fetch current weather for the destination(s)\n"
            "2. Use the get_current_time tool to check local time\n"
            "3. Optionally use search_restaurants to find dining options\n\n"
            "Then provide a weather analysis covering:\n"
            "- Current conditions and what to pack\n"
            "- Best outdoor activity windows\n"
            "- Weather-related travel advisories\n\n"
            "ALWAYS call the tools first — do NOT guess weather data.\n"
            "Output ONLY the weather analysis — no greetings or filler."
        ),
        tools=[mcp_tool],
    )

    return agent, mcp_tool
