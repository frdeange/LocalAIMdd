"""
Azure Foundry Local - OpenAI Client directo (workaround)
========================================================
Usa el cliente OpenAI estándar contra el endpoint local de Foundry,
evitando el bug de serialización del Agent Framework.

Demuestra:
  1. Conexión al runtime local de Foundry
  2. Listado de modelos del catálogo
  3. Function calling (tools) manual
  4. Respuesta no-streaming
  5. Respuesta streaming
  6. Manejo de errores
"""

import json
import sys
from datetime import datetime, timezone
from typing import Annotated

from foundry_local import FoundryLocalManager
from openai import OpenAI


# ──────────────────────────────────────────────
# Tools — definiciones JSON Schema para el modelo
# ──────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a given location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city or location to get the weather for.",
                    }
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time for a given timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_name": {
                        "type": "string",
                        "description": "Timezone name, e.g. 'UTC', 'US/Eastern', 'Europe/Madrid'.",
                    }
                },
                "required": ["timezone_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "Search for restaurants in a given city by cuisine type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city to search restaurants in.",
                    },
                    "cuisine": {
                        "type": "string",
                        "description": "Type of cuisine, e.g. 'Italian', 'Japanese', 'Mexican'.",
                    },
                },
                "required": ["city", "cuisine"],
            },
        },
    },
]


# ──────────────────────────────────────────────
# Tool implementations
# ──────────────────────────────────────────────

def get_weather(location: str) -> str:
    """Get the current weather for a given location."""
    weather_data = {
        "seattle": "Cloudy, 12°C, 80% humidity",
        "madrid": "Sunny, 28°C, 30% humidity",
        "amsterdam": "Rainy, 8°C, 90% humidity",
        "tokyo": "Clear skies, 22°C, 55% humidity",
        "london": "Foggy, 10°C, 85% humidity",
    }
    key = location.lower().strip()
    for city, weather in weather_data.items():
        if city in key:
            return f"Weather in {location}: {weather}"
    return f"Weather in {location}: Partly cloudy, 18°C, 60% humidity"


def get_current_time(timezone_name: str) -> str:
    """Get the current date and time for a given timezone."""
    now = datetime.now(timezone.utc)
    return f"Current time in {timezone_name}: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC (approximate)"


def search_restaurants(city: str, cuisine: str) -> str:
    """Search for restaurants in a given city by cuisine type."""
    restaurants = {
        ("madrid", "italian"): [
            "Trattoria Malatesta - Calle Lope de Vega 9 ★★★★☆",
            "Gioia Madrid - Calle de San Bartolomé 23 ★★★★★",
            "Cinquecento - Calle de Recoletos 6 ★★★★☆",
        ],
        ("seattle", "japanese"): [
            "Shiro's Sushi - 2401 2nd Ave ★★★★★",
            "Jiro Sushi - 1011 Pike St ★★★★☆",
            "Kamonegi - 1054 N 39th St ★★★★★",
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


# Dispatch table: name → function
TOOL_DISPATCH = {
    "get_weather": get_weather,
    "get_current_time": get_current_time,
    "search_restaurants": search_restaurants,
}


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a helpful local assistant powered by Foundry Local. "
    "You MUST use the provided tools to answer questions — do NOT answer from memory. "
    "Always call the appropriate tool first, then summarize the result concisely."
)


def call_with_tools(
    client: OpenAI,
    model: str,
    messages: list[dict],
    *,
    max_rounds: int = 5,
) -> str:
    """Send a chat completion request, handling tool calls in a loop.

    Returns the final assistant text response.
    """
    for round_num in range(max_rounds):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        choice = response.choices[0]

        # If the model wants to call tools
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            # Add assistant message with tool_calls
            messages.append(choice.message.model_dump())

            # Execute each tool and append results
            for tool_call in choice.message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                print(f"\n    🔧 Tool call: {fn_name}({fn_args})")

                fn = TOOL_DISPATCH.get(fn_name)
                if fn:
                    result = fn(**fn_args)
                else:
                    result = f"Error: unknown tool '{fn_name}'"
                print(f"    📋 Result: {result}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
            continue  # next round — let the model process tool results

        # Model finished with a text response
        return choice.message.content or "(no response)"

    return "(max tool-call rounds exceeded)"


def call_with_tools_streaming(
    client: OpenAI,
    model: str,
    messages: list[dict],
    *,
    max_rounds: int = 5,
) -> None:
    """Send a streaming chat completion request, handling tool calls.

    Prints tokens as they arrive. When tool calls are detected,
    executes them and continues in a new round.
    """
    for round_num in range(max_rounds):
        # Round 0 likely produces tool calls — Qwen leaks raw JSON as text
        # content alongside the proper tool_calls deltas, so we buffer text.
        # Subsequent rounds (after tool results) are the final answer — stream
        # tokens to the console in real time.
        stream_text = round_num > 0

        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            stream=True,
        )

        # Accumulate tool calls from the stream
        tool_calls_acc: dict[int, dict] = {}  # index → {id, name, arguments}
        content_acc = ""
        finish_reason = None

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason or finish_reason

            # Text content
            if delta.content:
                content_acc += delta.content
                if stream_text:
                    print(delta.content, end="", flush=True)

            # Accumulate tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name if tc.function and tc.function.name else "",
                            "arguments": "",
                        }
                    if tc.id:
                        tool_calls_acc[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_acc[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_acc[idx]["arguments"] += tc.function.arguments

        # Tool calls detected → discard leaked text, execute tools
        if tool_calls_acc:
            # Build assistant message with tool_calls
            assistant_tool_calls = []
            for idx in sorted(tool_calls_acc):
                tc = tool_calls_acc[idx]
                assistant_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                })
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": assistant_tool_calls,
            })

            # Execute tools
            for tc in assistant_tool_calls:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])
                print(f"\n    🔧 Tool call: {fn_name}({fn_args})")
                fn = TOOL_DISPATCH.get(fn_name)
                result = fn(**fn_args) if fn else f"Error: unknown tool '{fn_name}'"
                print(f"    📋 Result: {result}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
            continue  # next round

        # No tool calls — if we buffered (round 0), print now
        if not stream_text and content_acc:
            print(content_acc, end="")
        break

    print()  # final newline


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print(" Azure Foundry Local — OpenAI Client (workaround)")
    print("=" * 60)

    MODEL_ID = "qwen2.5-7b-instruct-cuda-gpu:4"

    # ── 1. Inicializar Foundry Local ────────────────────────
    print("\n▶ Initializing Foundry Local...")
    print("  (This may take a moment to bootstrap the service and download the model)\n")

    manager = FoundryLocalManager(bootstrap=True)
    manager.download_model(alias_or_model_id=MODEL_ID)
    manager.load_model(alias_or_model_id=MODEL_ID)

    client = OpenAI(
        base_url=manager.endpoint,
        api_key=manager.api_key,
    )

    print(f"  ✔ Connected! Using model: {MODEL_ID}")
    print(f"  ✔ Endpoint: {manager.endpoint}")

    # ── 2. Listar modelos del catálogo ──────────────────────
    print("\n▶ Available models in Foundry Local catalog:")
    print("-" * 55)

    catalog = manager.list_catalog_models()
    for model in catalog:
        tool_support = "✔ tools" if model.supports_tool_calling else "✘ no tools"
        print(f"  • {model.alias:<25} ({tool_support})  task={model.task}  id={model.id}")

    print(f"\n  Total: {len(catalog)} models")

    # ── 3. Respuesta no-streaming con tools ─────────────────
    print("\n" + "=" * 60)
    print(" Test 1: Non-streaming response (weather query)")
    print("=" * 60)

    query1 = "What's the weather like in Seattle right now?"
    print(f"\n  User: {query1}")
    print("  Agent: ", end="", flush=True)

    messages1 = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query1},
    ]
    result1 = call_with_tools(client, MODEL_ID, messages1)
    print(result1)

    # ── 4. Respuesta streaming con multi-tool ───────────────
    print("\n" + "=" * 60)
    print(" Test 2: Streaming response (multi-tool query)")
    print("=" * 60)

    query2 = "Find me some Italian restaurants in Madrid, and also tell me the current time in Europe/Madrid."
    print(f"\n  User: {query2}")
    print("  Agent: ", end="", flush=True)

    messages2 = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query2},
    ]
    call_with_tools_streaming(client, MODEL_ID, messages2)

    # ── 5. Otra consulta streaming ──────────────────────────
    print("\n" + "=" * 60)
    print(" Test 3: Multi-tool streaming (weather comparison)")
    print("=" * 60)

    query3 = "What's the weather in Tokyo and Amsterdam? Compare them briefly."
    print(f"\n  User: {query3}")
    print("  Agent: ", end="", flush=True)

    messages3 = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query3},
    ]
    call_with_tools_streaming(client, MODEL_ID, messages3)

    print("\n" + "=" * 60)
    print(" ✔ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
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
