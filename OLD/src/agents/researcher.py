"""
Researcher Agent
================
Gathers destination information: culture, attractions, transport, and travel tips.
Does NOT use external tools — relies on the LLM's knowledge.

This agent is the first step in the Travel Planner sequential workflow.
"""

from agent_framework import Agent


def create_researcher_agent(client: object) -> Agent:
    """Create the Researcher agent.

    Args:
        client: A FoundryLocalClient (or any client implementing as_agent).

    Returns:
        A configured Agent instance.
    """
    return client.as_agent(  # type: ignore[union-attr]
        name="Researcher",
        instructions=(
            "You are an expert travel researcher. Given a travel query, provide a concise "
            "research brief covering:\n"
            "1. Key attractions and points of interest\n"
            "2. Local culture and customs\n"
            "3. Transportation options\n"
            "4. Best time to visit\n"
            "5. Practical travel tips\n\n"
            "Be factual, concise, and well-organized. Use bullet points.\n"
            "Output ONLY the research brief — no greetings or filler."
        ),
    )
