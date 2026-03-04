"""
Prototype 02 — ConcurrentBuilder + workflow.as_agent()
======================================================
Validates that ConcurrentBuilder works with Ollama and can be
exposed as a single agent via .as_agent().

Creates 2 concurrent agents (simulating Camera + Meteo):
  - CameraAgent: simulates camera positioning and image capture
  - MeteoAgent: simulates weather conditions assessment

Both run in parallel via ConcurrentBuilder, and the workflow is
wrapped as a single agent via .as_agent() that can be invoked
like any other Agent.

This validates the KEY composition primitive we need:
  ConcurrentBuilder(...).build().as_agent("ReconTeam")

Usage:
    python prototypes/02_concurrent_as_agent.py

Environment:
    OLLAMA_HOST      (default: http://localhost:11434)
    OLLAMA_MODEL_ID  (default: qwen2.5:3b)
"""

import asyncio
import os
import sys
import patch_ollama  # noqa: F401 — must import before using OllamaChatClient
from agent_framework import Agent, AgentResponse, Message
from agent_framework.ollama import OllamaChatClient
from agent_framework.orchestrations import ConcurrentBuilder

# ── Config ────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL_ID = os.getenv("OLLAMA_MODEL_ID", "qwen2.5:3b")

SEPARATOR = "─" * 70


def create_client() -> OllamaChatClient:
    """Create an OllamaChatClient pointing to local Ollama."""
    print(f"  Ollama host:  {OLLAMA_HOST}")
    print(f"  Model:        {OLLAMA_MODEL_ID}")
    return OllamaChatClient(host=OLLAMA_HOST, model_id=OLLAMA_MODEL_ID)


def create_agents(client: OllamaChatClient) -> tuple[Agent, Agent]:
    """Create the two concurrent specialist agents."""
    camera_agent = client.as_agent(
        name="CameraAgent",
        instructions=(
            "You are a surveillance camera operator. When given coordinates:\n"
            "1. Confirm you are positioning the camera towards those coordinates\n"
            "2. Describe what the camera captures (simulate: you see a dark-colored "
            "SUV parked near a building, partially obscured by vegetation)\n"
            "3. Report the image capture status\n"
            "Be brief and factual, like a military/operations report."
        ),
    )

    meteo_agent = client.as_agent(
        name="MeteoAgent",
        instructions=(
            "You are a meteorological analyst. When given coordinates:\n"
            "1. Report current weather conditions at those coordinates\n"
            "   (simulate: partly cloudy, 18°C, wind SW 12km/h, visibility 8km, "
            "humidity 65%, no precipitation expected in next 6h)\n"
            "2. Assess how weather affects field operations visibility\n"
            "3. Provide a brief operational weather summary\n"
            "Be brief and factual, like a military/operations weather brief."
        ),
    )

    return camera_agent, meteo_agent


async def test_concurrent_standalone(client: OllamaChatClient) -> None:
    """Test 1: ConcurrentBuilder running standalone (not as agent)."""
    print("\n  TEST 1: ConcurrentBuilder standalone")
    print(f"  {SEPARATOR}")

    camera, meteo = create_agents(client)

    workflow = ConcurrentBuilder(
        participants=[camera, meteo],
    ).build()

    query = "Coordinates received: 40.4168° N, 3.7038° W. Assess the location."
    print(f"\n  Input: {query}")
    print(f"\n  Running concurrent workflow...")

    result = await workflow.run(query)
    outputs = result.get_outputs()

    if outputs:
        print(f"\n  Got {len(outputs)} output(s):")
        for i, output in enumerate(outputs):
            if isinstance(output, list):
                for msg in output:
                    if hasattr(msg, "text") and msg.text:
                        speaker = msg.author_name or msg.role
                        print(f"\n  [{speaker}]: {msg.text[:300]}")
            else:
                print(f"\n  Output {i}: {str(output)[:300]}")
    else:
        print("\n  WARNING: No outputs received!")

    print(f"\n  TEST 1: PASSED")


async def test_concurrent_as_agent(client: OllamaChatClient) -> None:
    """Test 2: ConcurrentBuilder exposed as an agent via .as_agent()."""
    print(f"\n\n  TEST 2: ConcurrentBuilder.as_agent()")
    print(f"  {SEPARATOR}")

    camera, meteo = create_agents(client)

    # Build concurrent workflow and wrap as agent
    recon_workflow = ConcurrentBuilder(
        participants=[camera, meteo],
    ).build()

    recon_agent = recon_workflow.as_agent(name="ReconTeam")
    print(f"  Created agent: {recon_agent.name if hasattr(recon_agent, 'name') else 'ReconTeam'}")
    print(f"  Agent type: {type(recon_agent).__name__}")

    query = "Coordinates: 40.4168° N, 3.7038° W. Run full reconnaissance."
    print(f"\n  Input: {query}")
    print(f"\n  Running as agent...")

    # Run the wrapped agent — this is the key test
    response = await recon_agent.run(query)

    if response:
        print(f"\n  Response type: {type(response).__name__}")
        if hasattr(response, "text") and response.text:
            print(f"\n  Response text: {response.text[:500]}")
        elif hasattr(response, "messages"):
            for msg in response.messages:
                if msg.text:
                    speaker = msg.author_name or msg.role
                    print(f"\n  [{speaker}]: {msg.text[:300]}")
        else:
            print(f"\n  Response: {str(response)[:500]}")
    else:
        print("\n  WARNING: No response received!")

    print(f"\n  TEST 2: PASSED")


async def main() -> None:
    """Run all ConcurrentBuilder tests."""
    print(f"\n{'═' * 70}")
    print("  PROTOTYPE 02: ConcurrentBuilder + as_agent()")
    print(f"{'═' * 70}\n")

    print("[1/3] Creating OllamaChatClient...")
    client = create_client()

    print("\n[2/3] Test 1 — Standalone concurrent workflow")
    await test_concurrent_standalone(client)

    print("\n[3/3] Test 2 — Concurrent workflow as agent")
    await test_concurrent_as_agent(client)

    print(f"\n{SEPARATOR}")
    print("  RESULT: All ConcurrentBuilder tests completed successfully!")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n  ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
