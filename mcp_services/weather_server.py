"""
MCP Weather Service — Simulated Meteorological Data
=====================================================
FastMCP server that provides deterministic weather data
based on coordinate sectors. All data is mocked.

Run:  python -m mcp_services.weather_server
Default: streamable-http on port 8091
"""

import asyncio
import json
import os
from typing import Annotated

from mcp_services.telemetry import configure_telemetry

configure_telemetry("mcp-weather")

from fastmcp import FastMCP

mcp = FastMCP(
    name="BMS Weather Service",
    instructions="Simulated meteorological service. Provides weather conditions and operational impact assessment for given coordinates.",
)

# ── Deterministic sector-based weather data ───────────────────
WEATHER_DATA: dict[str, dict] = {
    "NE": {
        "temperature_c": 18.5,
        "conditions": "Partly cloudy",
        "wind_speed_kmh": 15,
        "wind_direction": "NW",
        "visibility_km": 8.0,
        "humidity_pct": 62,
        "precipitation": "None",
        "risk_level": "LOW",
        "operational_impact": "Good conditions for ground and air operations. Slight crosswind may affect precision optics.",
        "forecast_6h": "Clearing skies, temperature dropping to 14°C. Visibility improving to 12+ km.",
    },
    "NW": {
        "temperature_c": 12.0,
        "conditions": "Overcast, light drizzle",
        "wind_speed_kmh": 25,
        "wind_direction": "SW",
        "visibility_km": 3.5,
        "humidity_pct": 88,
        "precipitation": "Light rain (2mm/h)",
        "risk_level": "MODERATE",
        "operational_impact": "Reduced visibility limits surveillance range. Wet roads may affect vehicle mobility. Helo operations marginal.",
        "forecast_6h": "Rain intensifying to moderate (5mm/h). Visibility dropping to 1.5 km. Wind gusts to 40 km/h.",
    },
    "SE": {
        "temperature_c": 32.0,
        "conditions": "Clear, haze",
        "wind_speed_kmh": 8,
        "wind_direction": "E",
        "visibility_km": 5.0,
        "humidity_pct": 45,
        "precipitation": "None",
        "risk_level": "LOW",
        "operational_impact": "Heat haze may degrade long-range optics. Otherwise favourable for all operations.",
        "forecast_6h": "Stable conditions. Temperature peaking at 35°C. Heat advisory for prolonged exposure.",
    },
    "SW": {
        "temperature_c": 5.0,
        "conditions": "Dense fog",
        "wind_speed_kmh": 3,
        "wind_direction": "N",
        "visibility_km": 0.3,
        "humidity_pct": 98,
        "precipitation": "None (fog moisture)",
        "risk_level": "HIGH",
        "operational_impact": "Severe visibility restriction. Ground surveillance ineffective beyond 100m. Air operations NOT recommended. Thermal imaging advised.",
        "forecast_6h": "Fog lifting by mid-morning. Visibility recovering to 5 km. Temperature rising to 10°C.",
    },
}


@mcp.tool()
async def get_weather_report(
    latitude: Annotated[float, "Target latitude in decimal degrees"],
    longitude: Annotated[float, "Target longitude in decimal degrees"],
) -> str:
    """Get current weather conditions and operational impact assessment for the given coordinates.

    Returns a JSON report with temperature, conditions, wind, visibility,
    risk level, operational impact, and 6-hour forecast.
    """
    # Simulate weather service query delay
    await asyncio.sleep(0.5)

    ns = "N" if latitude >= 0 else "S"
    ew = "E" if longitude >= 0 else "W"
    sector_key = ns + ew

    data = dict(WEATHER_DATA.get(sector_key, WEATHER_DATA["NE"]))
    data["coordinates"] = {"latitude": latitude, "longitude": longitude}
    data["sector"] = sector_key
    data["station_status"] = "OPERATIONAL"
    data["timestamp"] = "SIMULATED"

    return json.dumps(data, indent=2)


if __name__ == "__main__":
    port = int(os.getenv("WEATHER_SERVER_PORT", "8091"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
