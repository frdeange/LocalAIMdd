"""
Shared agent factories for prototypes 06, 07, 08.
===================================================
All three prototypes share the same specialist agents with the same
instructions and MCP tool configuration. Only the orchestration
pattern differs.

Model: qwen3.5:4b (configured via OLLAMA_MODEL_ID env var)
MCP:   Camera :8090, Weather :8091, BMS :8093
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import src.patch_ollama  # noqa: F401 — must be imported before any client usage

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.ollama import OllamaChatClient
from src.config import (
    MCP_BMS_URL,
    MCP_CAMERA_URL,
    MCP_WEATHER_URL,
    OLLAMA_HOST,
    OLLAMA_MODEL_ID,
)

SEP = "-" * 60


# ── Orchestrator (only used by HandoffBuilder prototype) ──────

ORCHESTRATOR_INSTRUCTIONS = (
    "You are a military operations coordinator receiving field reports. "
    "Your ONLY job is to route messages to the right specialist. "
    "NEVER answer operational questions yourself.\n\n"
    "When a field operator reports a new situation:\n"
    "  1. First, route to the case manager to log the incident.\n"
    "  2. Then, route to the field specialist for reconnaissance.\n\n"
    "When the operator provides additional information (coordinates, "
    "vehicle details), route to the field specialist.\n\n"
    "When the operator asks to update or close a case, route to the "
    "case manager.\n\n"
    "Always respond in the same language as the operator. "
    "Plain text only, no markdown."
)


def create_orchestrator(client: OllamaChatClient) -> Agent:
    """Create the Orchestrator — routes messages, never answers directly."""
    return client.as_agent(
        name="Orchestrator",
        instructions=ORCHESTRATOR_INSTRUCTIONS,
    )


# ── CaseManager ──────────────────────────────────────────────

CASE_MANAGER_INSTRUCTIONS = (
    "You are a case management officer in a battlefield management system. "
    "Your job is to create and manage incident cases using your tools.\n\n"
    "When you receive a new situation report:\n"
    "  - Create a case immediately using your tools.\n"
    "  - Extract the summary, priority and any coordinates from the message.\n"
    "  - Confirm the case ID to the operator.\n\n"
    "When you receive updated information or new findings:\n"
    "  - Update the existing case or add an interaction record.\n\n"
    "After completing each task (creating or updating a case), "
    "transfer control back so the conversation can continue. "
    "Do not keep working on your own after your task is done.\n\n"
    "ALWAYS use your tools — never make up case IDs or data.\n"
    "Respond in the same language as the operator. "
    "Plain text only, no markdown."
)


def create_case_manager(client: OllamaChatClient) -> Agent:
    """Create the CaseManager agent with MCP BMS tools."""
    bms_mcp = MCPStreamableHTTPTool(
        name="bms_mcp",
        url=MCP_BMS_URL,
        description="BMS case management database — create, update, and query incident cases",
    )
    return client.as_agent(
        name="CaseManager",
        instructions=CASE_MANAGER_INSTRUCTIONS,
        tools=[bms_mcp],
    )


# ── FieldSpecialist ──────────────────────────────────────────

FIELD_SPECIALIST_INSTRUCTIONS = (
    "You are a tactical field analyst supporting military operations. "
    "You have access to surveillance cameras and weather stations.\n\n"
    "CRITICAL RULE: You MUST have explicit coordinates (latitude and "
    "longitude) from the operator BEFORE using any sensor tool. "
    "If the operator has NOT provided coordinates, your ONLY response "
    "must be to ask for them. Do NOT assume, guess, or invent coordinates.\n\n"
    "Once you have coordinates:\n"
    "  1. Use your camera sensor to check the area.\n"
    "  2. Use your weather station to assess conditions.\n"
    "  3. Provide a concise tactical assessment (3-5 sentences).\n\n"
    "Your sensor tools return data in English, but you MUST respond in "
    "the SAME LANGUAGE the operator used.\n"
    "Plain text only, no markdown."
)


def create_field_specialist(client: OllamaChatClient) -> Agent:
    """Create the FieldSpecialist agent with MCP Camera + Weather tools."""
    camera_mcp = MCPStreamableHTTPTool(
        name="camera_mcp",
        url=MCP_CAMERA_URL,
        description="Surveillance camera system — get visual observations for given coordinates",
    )
    weather_mcp = MCPStreamableHTTPTool(
        name="weather_mcp",
        url=MCP_WEATHER_URL,
        description="Weather station — get weather conditions for given coordinates",
    )
    return client.as_agent(
        name="FieldSpecialist",
        instructions=FIELD_SPECIALIST_INSTRUCTIONS,
        tools=[camera_mcp, weather_mcp],
    )


# ── Client factory ───────────────────────────────────────────

def get_client() -> OllamaChatClient:
    """Get an OllamaChatClient configured from environment (with patch applied)."""
    from src.client import get_client as _get_client
    return _get_client()


# ── Configuration display ─────────────────────────────────────

def print_config(prototype_name: str, pattern: str) -> None:
    """Print startup configuration for any prototype."""
    print(SEP)
    print(f"  {prototype_name}")
    print(f"  Pattern: {pattern}")
    print(SEP)
    print(f"  Model:       {OLLAMA_MODEL_ID}")
    print(f"  Ollama:      {OLLAMA_HOST}")
    print(f"  MCP Camera:  {MCP_CAMERA_URL}")
    print(f"  MCP Weather: {MCP_WEATHER_URL}")
    print(f"  MCP BMS:     {MCP_BMS_URL}")
    print(SEP)


# ── Shared event processing ──────────────────────────────────

def print_agent_message(speaker: str, text: str, max_len: int = 800) -> None:
    """Print an agent message with consistent formatting."""
    display = text[:max_len]
    if len(text) > max_len:
        display += "..."
    print(f"\n  [{speaker}]: {display}")


def print_handoff(source: str, target: str) -> None:
    """Print a handoff event."""
    print(f"  >> HANDOFF: {source} -> {target}")
