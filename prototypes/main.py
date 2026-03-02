"""
Azure Foundry Local - Agent Framework + MCP Server
===================================================
Demuestra:
  1. Conexión al runtime local de Foundry
  2. Listado de modelos del catálogo
  3. Agente con tools vía MCP (Model Context Protocol)
  4. Respuesta no-streaming
  5. Respuesta streaming
  6. Manejo de errores

Las tools se sirven desde mcp_server.py (FastMCP, transporte stdio).
"""

import asyncio
import sys

from agent_framework_foundry_local import FoundryLocalClient
from agent_framework import MCPStdioTool


# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

MODEL_ID = "qwen2.5-7b-instruct-cuda-gpu:4"
MCP_SERVER_CMD = sys.executable          # python.exe from this venv
MCP_SERVER_ARGS = ["mcp_server.py"]


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

async def main() -> None:
    print("=" * 60)
    print(" Azure Foundry Local — Agent Framework + MCP")
    print("=" * 60)

    # ── 1. Inicializar cliente ──────────────────────────────
    print("\n▶ Initializing Foundry Local client...")
    print("  (This may take a moment to bootstrap the service and download the model)\n")

    client = FoundryLocalClient(
        model_id=MODEL_ID,
        bootstrap=True,
        prepare_model=True,
    )

    print(f"  ✔ Connected! Using model: {client.model_id}")
    print(f"  ✔ Endpoint: {client.manager.endpoint}")

    # ── 2. Listar modelos del catálogo ──────────────────────
    print("\n▶ Available models in Foundry Local catalog:")
    print("-" * 55)

    catalog = client.manager.list_catalog_models()
    for model in catalog:
        tool_support = "✔ tools" if model.supports_tool_calling else "✘ no tools"
        print(f"  • {model.alias:<25} ({tool_support})  task={model.task}  id={model.id}")

    print(f"\n  Total: {len(catalog)} models")

    # ── 3. Conectar MCP server + crear agente ───────────────
    print("\n▶ Connecting to MCP server (FastMCP via stdio)...")

    mcp_tool = MCPStdioTool(
        name="local_tools",
        command=MCP_SERVER_CMD,
        args=MCP_SERVER_ARGS,
        description="Local tools: weather, time, restaurants",
    )

    async with mcp_tool:
        # Show discovered tools
        tool_names = [f.name for f in mcp_tool.functions]
        print(f"  ✔ MCP connected! Discovered {len(tool_names)} tools: {', '.join(tool_names)}")

        agent = client.as_agent(
            name="LocalAssistant",
            instructions=(
                "You are a helpful local assistant powered by Foundry Local. "
                "You MUST use the provided tools to answer questions — do NOT answer from memory. "
                "Always call the appropriate tool first, then summarize the result concisely."
            ),
            tools=[mcp_tool],
            default_options={"tool_choice": "auto"},
        )

        print("  ✔ Agent 'LocalAssistant' ready with MCP tools")

        # ── 4. Respuesta no-streaming ───────────────────────
        print("\n" + "=" * 60)
        print(" Test 1: Non-streaming response (weather query)")
        print("=" * 60)

        query1 = "What's the weather like in Seattle right now?"
        print(f"\n  User: {query1}")
        print("  Agent: ", end="", flush=True)

        result = await agent.run(query1)
        print(result)

        # ── 5. Respuesta streaming ──────────────────────────
        print("\n" + "=" * 60)
        print(" Test 2: Streaming response (multi-tool query)")
        print("=" * 60)

        query2 = "Find me some Italian restaurants in Madrid, and also tell me the current time in Europe/Madrid."
        print(f"\n  User: {query2}")
        print("  Agent: ", end="", flush=True)

        async for chunk in agent.run(query2, stream=True):
            if chunk.text:
                print(chunk.text, end="", flush=True)

        print()

        # ── 6. Otra consulta streaming ──────────────────────
        print("\n" + "=" * 60)
        print(" Test 3: Multi-tool streaming (weather comparison)")
        print("=" * 60)

        query3 = "What's the weather in Tokyo and Amsterdam? Compare them briefly."
        print(f"\n  User: {query3}")
        print("  Agent: ", end="", flush=True)

        async for chunk in agent.run(query3, stream=True):
            if chunk.text:
                print(chunk.text, end="", flush=True)

        print()

    print("\n" + "=" * 60)
    print(" ✔ All tests completed! MCP server shut down.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ConnectionError as e:
        print(f"\n✘ Connection Error: Could not connect to Foundry Local runtime.")
        print(f"  Make sure the Foundry Local service is installed and running.")
        print(f"  Details: {e}")
        sys.exit(1)
    except TimeoutError as e:
        print(f"\n✘ Timeout: The model took too long to respond.")
        print(f"  This may happen with large models on limited hardware.")
        print(f"  Details: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n  Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        error_msg = str(e).lower()
        if "model" in error_msg and ("not found" in error_msg or "not available" in error_msg):
            print(f"\n✘ Model Error: The requested model is not available.")
            print(f"  Try running: foundry model list")
            print(f"  Details: {e}")
        elif "connection" in error_msg or "refused" in error_msg:
            print(f"\n✘ Service Error: Foundry Local service is not reachable.")
            print(f"  Start it with: foundry service start")
            print(f"  Details: {e}")
        else:
            print(f"\n✘ Unexpected Error: {type(e).__name__}: {e}")
        sys.exit(1)
