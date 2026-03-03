"""
OllamaChatClient factory.

Provides a single ``get_client()`` function so every module shares the
same configuration and the patch is guaranteed to be applied first.
"""

import src.patch_ollama  # noqa: F401 — apply monkey-patch before import

from agent_framework.ollama import OllamaChatClient

from src.config import OLLAMA_HOST, OLLAMA_MODEL_ID


def get_client() -> OllamaChatClient:
    """Return an OllamaChatClient configured from environment."""
    return OllamaChatClient(host=OLLAMA_HOST, model_id=OLLAMA_MODEL_ID)
