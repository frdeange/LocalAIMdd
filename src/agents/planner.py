"""
Planner Agent
=============
Synthesizes research and weather data into a complete travel itinerary.
Does NOT use external tools — works with the context from previous agents.

This agent is the final step in the Travel Planner sequential workflow.
"""

from agent_framework import Agent


def create_planner_agent(client: object) -> Agent:
    """Create the Planner agent.

    Args:
        client: A FoundryLocalClient (or any client implementing as_agent).

    Returns:
        A configured Agent instance.
    """
    return client.as_agent(  # type: ignore[union-attr]
        name="Planner",
        instructions=(
            "You are a professional travel planner. Based on the research brief and "
            "weather analysis from the previous agents, create a complete travel plan:\n\n"
            "1. **Day-by-Day Itinerary**: Suggest a 3-day itinerary with morning, "
            "afternoon, and evening activities\n"
            "2. **Packing List**: Based on weather conditions\n"
            "3. **Budget Estimate**: Rough daily budget in USD\n"
            "4. **Restaurant Recommendations**: If dining data is available\n"
            "5. **Pro Tips**: Insider advice for the destination\n\n"
            "Make the plan practical, well-structured, and actionable.\n"
            "Output ONLY the travel plan — no greetings or filler."
        ),
    )
