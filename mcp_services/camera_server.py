"""
MCP Camera Service — Simulated Surveillance Camera
====================================================
FastMCP server that simulates a pan-tilt-zoom camera system.
Returns deterministic observation data based on coordinate sectors.

Run:  python -m mcp_services.camera_server
Default: streamable-http on port 8090
"""

import asyncio
import json
import os
from typing import Annotated

from mcp_services.telemetry import configure_telemetry

configure_telemetry("mcp-camera")

from fastmcp import FastMCP

mcp = FastMCP(
    name="BMS Camera Service",
    instructions="Simulated surveillance camera system. Provides visual observation data for given coordinates.",
)

# ── Deterministic sector-based simulation data ────────────────
# Coordinates mapped to quadrants: lat >= 0 → N, lon >= 0 → E
SECTORS: dict[str, dict] = {
    "NE": {
        "target_description": "Dark green SUV parked adjacent to a two-story warehouse. No visible markings or insignia. Single occupant observed exiting the vehicle.",
        "environment": "Industrial zone, paved lot, several shipping containers nearby.",
        "image_quality": "Good — clear skies, moderate ambient light.",
        "zoom_level_used": 5,
        "tactical_notes": "Vehicle positioned with clear line of sight to main access road. Possible surveillance position.",
    },
    "NW": {
        "target_description": "Open agricultural field. No vehicles or personnel detected within 500m radius.",
        "environment": "Flat terrain, low vegetation, unpaved farm track to the east.",
        "image_quality": "Good — wide-open area, no obstructions.",
        "zoom_level_used": 3,
        "tactical_notes": "Area appears clear. No activity of interest.",
    },
    "SE": {
        "target_description": "Two military-type trucks in convoy formation on secondary road. Canvas-covered cargo beds. Lead vehicle has roof-mounted antenna.",
        "environment": "Rural road, hilly terrain, tree line 200m to the south.",
        "image_quality": "Moderate — partial tree canopy interference.",
        "zoom_level_used": 7,
        "tactical_notes": "Convoy heading northeast at approximately 40 km/h. Antenna suggests command vehicle.",
    },
    "SW": {
        "target_description": "Civilian white sedan, single occupant, parked on roadside shoulder. Hazard lights active.",
        "environment": "Two-lane road, residential area, low-rise buildings.",
        "image_quality": "Good — street lighting supplementing daylight.",
        "zoom_level_used": 4,
        "tactical_notes": "Appears to be a disabled civilian vehicle. Low threat assessment.",
    },
}


def _get_sector(latitude: float, longitude: float) -> str:
    """Map coordinates to a quadrant sector key."""
    ns = "N" if latitude >= 0 else "S"
    ew = "E" if longitude >= 0 else "W"
    key = ns + ew
    # Map S* sectors to existing data (wrap around)
    return SECTORS.get(key, SECTORS.get("N" + ew, SECTORS["NE"]))  # type: ignore


@mcp.tool()
async def get_camera_feed(
    latitude: Annotated[float, "Target latitude in decimal degrees"],
    longitude: Annotated[float, "Target longitude in decimal degrees"],
    zoom_level: Annotated[int, "Camera zoom level (1-10, default 5)"] = 5,
) -> str:
    """Reposition the surveillance camera to the given coordinates and capture visual observation data.

    Returns a JSON report with target description, environment, image quality, and tactical notes.
    """
    # Simulate camera repositioning delay
    await asyncio.sleep(1.0)

    ns = "N" if latitude >= 0 else "S"
    ew = "E" if longitude >= 0 else "W"
    sector_key = ns + ew

    data = dict(SECTORS.get(sector_key, SECTORS["NE"]))
    data["coordinates"] = {"latitude": latitude, "longitude": longitude}
    data["sector"] = sector_key
    data["zoom_level_requested"] = zoom_level
    data["camera_status"] = "OPERATIONAL"
    data["timestamp"] = "SIMULATED"

    return json.dumps(data, indent=2)


if __name__ == "__main__":
    port = int(os.getenv("MCP_CAMERA_PORT", "8090"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
