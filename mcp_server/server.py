"""
FastMCP Travel Tools Server
============================
Provides travel-related tools via Model Context Protocol (MCP).
Runs as a Streamable HTTP server on port 8090, no authentication.

Tools:
    - get_weather: Current weather for a location
    - get_current_time: Current date/time for a timezone
    - search_restaurants: Restaurant search by city and cuisine
"""

from datetime import datetime, timezone
from typing import Annotated

from fastmcp import FastMCP

# ──────────────────────────────────────────────────────────────
# Server Setup
# ──────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="TravelTools",
    instructions="Travel-related tools for weather, time, and restaurant search.",
)


# ──────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────

@mcp.tool()
def get_weather(
    location: Annotated[str, "The city or location to get weather for"],
) -> str:
    """Get the current weather for a given location."""
    weather_data = {
        "seattle": "Cloudy, 12°C, 80% humidity, light rain expected",
        "madrid": "Sunny, 28°C, 30% humidity, clear skies",
        "amsterdam": "Rainy, 8°C, 90% humidity, strong winds",
        "tokyo": "Clear skies, 22°C, 55% humidity, pleasant",
        "london": "Foggy, 10°C, 85% humidity, overcast",
        "paris": "Partly cloudy, 18°C, 65% humidity, mild breeze",
        "new york": "Sunny, 24°C, 50% humidity, warm",
        "barcelona": "Sunny, 26°C, 40% humidity, sea breeze",
        "rome": "Warm, 30°C, 35% humidity, clear skies",
        "berlin": "Overcast, 14°C, 75% humidity, cool",
        "lisbon": "Sunny, 25°C, 45% humidity, light wind",
        "bangkok": "Hot and humid, 34°C, 80% humidity, chance of thunderstorms",
        "sydney": "Partly cloudy, 20°C, 60% humidity, mild",
    }

    key = location.lower().strip()
    for city, weather in weather_data.items():
        if city in key:
            return f"Weather in {location}: {weather}"

    return f"Weather in {location}: Partly cloudy, 18°C, 60% humidity (default estimate)"


@mcp.tool()
def get_current_time(
    timezone_name: Annotated[str, "Timezone name, e.g. 'UTC', 'US/Eastern', 'Europe/Madrid'"],
) -> str:
    """Get the current date and time for a given timezone."""
    try:
        import zoneinfo

        tz = zoneinfo.ZoneInfo(timezone_name)
        now = datetime.now(tz)
        return f"Current time in {timezone_name}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    except Exception:
        now = datetime.now(timezone.utc)
        return f"Current time (UTC, '{timezone_name}' not resolved): {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"


@mcp.tool()
def search_restaurants(
    city: Annotated[str, "The city to search restaurants in"],
    cuisine: Annotated[str, "Type of cuisine, e.g. 'Italian', 'Japanese', 'Mexican'"],
) -> str:
    """Search for restaurants in a given city by cuisine type."""
    restaurants = {
        ("madrid", "italian"): [
            "Trattoria Malatesta - Calle Lope de Vega 9 ★★★★☆",
            "Gioia Madrid - Calle de San Bartolomé 23 ★★★★★",
            "Cinquecento - Calle de Recoletos 6 ★★★★☆",
        ],
        ("madrid", "spanish"): [
            "Botín - Calle de Cuchilleros 17 ★★★★★ (world's oldest restaurant)",
            "Casa Lucio - Calle de la Cava Baja 35 ★★★★☆",
            "StreetXO - Calle de Serrano 52 ★★★★☆",
        ],
        ("tokyo", "japanese"): [
            "Sukiyabashi Jiro - Ginza ★★★★★",
            "Ichiran Ramen - Shibuya ★★★★☆",
            "Tsukiji Tamasuji - Tsukiji ★★★★★",
        ],
        ("tokyo", "ramen"): [
            "Fuunji - Shinjuku ★★★★★",
            "Afuri - Ebisu ★★★★☆",
            "Ichiran - Multiple locations ★★★★☆",
        ],
        ("paris", "french"): [
            "Le Comptoir du Panthéon - Rue Soufflot ★★★★☆",
            "Chez Janou - Rue Roger Verlomme ★★★★★",
            "Le Bouillon Chartier - Rue du Faubourg Montmartre ★★★★☆",
        ],
        ("barcelona", "spanish"): [
            "Cal Pep - Plaça de les Olles ★★★★★",
            "Tickets - Avinguda del Paral·lel ★★★★★",
            "Els Quatre Gats - Carrer de Montsió ★★★★☆",
        ],
        ("seattle", "japanese"): [
            "Shiro's Sushi - 2401 2nd Ave ★★★★★",
            "Jiro Sushi - 1011 Pike St ★★★★☆",
            "Kamonegi - 1054 N 39th St ★★★★★",
        ],
        ("amsterdam", "dutch"): [
            "De Silveren Spiegel - Kattengat 4-6 ★★★★★",
            "Moeders - Rozengracht 251 ★★★★☆",
            "Haesje Claes - Spuistraat 275 ★★★★☆",
        ],
    }

    key = (city.lower().strip(), cuisine.lower().strip())
    if key in restaurants:
        results = "\n".join(f"  • {r}" for r in restaurants[key])
        return f"Restaurants in {city} ({cuisine} cuisine):\n{results}"

    return (
        f"Found some {cuisine} restaurants in {city}:\n"
        f"  • The {cuisine} Kitchen - Downtown ★★★★☆\n"
        f"  • Casa {cuisine} - Old Town ★★★☆☆\n"
        f"  • {cuisine} Bistro - Riverside ★★★★★"
    )


# ──────────────────────────────────────────────────────────────
# Health Check (excluded from OTel traces via OTEL_PYTHON_EXCLUDED_URLS)
# ──────────────────────────────────────────────────────────────

@mcp.custom_route("/health", methods=["GET"], name="health_check", include_in_schema=False)
async def health_check(request):
    """Lightweight health endpoint for Docker healthcheck — no MCP overhead."""
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "healthy", "service": "travel-mcp-tools"})


# ──────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8090)
