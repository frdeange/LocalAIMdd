"""
Monkey-patch for agent_framework_ollama to strip unsupported kwargs.

The MAF Ollama adapter passes **kwargs directly to ollama.AsyncClient.chat(),
but HandoffBuilder injects kwargs like `allow_multiple_tool_calls` that the
Ollama Python client doesn't support, causing a TypeError.

This patch wraps ollama.AsyncClient.chat() itself to strip any kwargs not in
its explicit signature, so no matter how MAF calls it, invalid kwargs are
dropped.

Usage:
    import patch_ollama  # noqa: F401  — must import before using OllamaChatClient
"""

import functools
import inspect
from typing import Any


def _apply_patch() -> None:
    import ollama

    original_chat = ollama.AsyncClient.chat

    if getattr(original_chat, "_patched_for_kwargs", False):
        return  # Already patched

    # Get the valid parameter names from the original signature
    valid_params = set(inspect.signature(original_chat).parameters.keys())
    # Remove 'self' since it's passed positionally
    valid_params.discard("self")

    @functools.wraps(original_chat)
    async def _patched_chat(self: Any, *args: Any, **kwargs: Any) -> Any:
        # Strip kwargs not in the original signature
        filtered = {k: v for k, v in kwargs.items() if k in valid_params}
        dropped = set(kwargs.keys()) - set(filtered.keys())
        if dropped:
            pass  # silently drop unsupported kwargs
        return await original_chat(self, *args, **filtered)

    _patched_chat._patched_for_kwargs = True  # type: ignore[attr-defined]
    ollama.AsyncClient.chat = _patched_chat  # type: ignore[attr-defined]
    print("  [patch_ollama] Applied kwargs filter to ollama.AsyncClient.chat()")


_apply_patch()
