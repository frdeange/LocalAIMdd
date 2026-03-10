"""
Monkey-patch for agent_framework_ollama — strips unsupported kwargs.

Bug: MAF's HandoffBuilder injects kwargs like ``allow_multiple_tool_calls``
into ``_inner_get_response()``, which are forwarded via ``**kwargs`` to
``ollama.AsyncClient.chat()``.  The Ollama Python client doesn't accept
them, raising ``TypeError``.

Tracked upstream: https://github.com/microsoft/agent-framework/issues/4402

This module must be imported **before** any ``OllamaChatClient`` usage::

    import src.patch_ollama  # noqa: F401
"""

import functools
import inspect
from typing import Any


def _apply_patch() -> None:
    import ollama
    from src.config import OLLAMA_THINK

    original_chat = ollama.AsyncClient.chat

    if getattr(original_chat, "_patched_for_kwargs", False):
        return  # Already patched

    valid_params = set(inspect.signature(original_chat).parameters.keys())
    valid_params.discard("self")

    @functools.wraps(original_chat)
    async def _patched_chat(self: Any, *args: Any, **kwargs: Any) -> Any:
        filtered = {k: v for k, v in kwargs.items() if k in valid_params}
        # Inject think setting unless explicitly provided by caller
        if "think" not in filtered:
            filtered["think"] = OLLAMA_THINK
        return await original_chat(self, *args, **filtered)

    _patched_chat._patched_for_kwargs = True  # type: ignore[attr-defined]
    ollama.AsyncClient.chat = _patched_chat  # type: ignore[attr-defined]


_apply_patch()
