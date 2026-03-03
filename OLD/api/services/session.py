"""
Multi-Turn Session Service
==========================
Builds conversation context from PostgreSQL history for multi-turn interactions.
Formats previous messages as a structured prefix to the user query, respecting
a configurable token budget.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.orm import Message

logger = logging.getLogger(__name__)

# Rough estimate: 1 token ≈ 4 characters
MAX_CONTEXT_CHARS = 4096 * 4  # ~4096 tokens


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (1 token ≈ 4 chars)."""
    return len(text) // 4


def build_context_prefix(messages: list[Message], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Build a structured context prefix from conversation history.

    Takes the most recent messages that fit within the token budget and
    formats them as a conversation summary for the LLM.

    Args:
        messages: List of Message ORM objects, ordered by step_number.
        max_chars: Maximum character budget for the context.

    Returns:
        A formatted string prefix, or empty string if no history.
    """
    if not messages:
        return ""

    # Build context from most recent messages, working backwards
    context_parts: list[str] = []
    total_chars = 0

    for msg in reversed(messages):
        author = msg.author_name or msg.role.capitalize()
        entry = f"[{author}]: {msg.content}"

        if total_chars + len(entry) > max_chars:
            break

        context_parts.insert(0, entry)
        total_chars += len(entry)

    if not context_parts:
        return ""

    header = "=== PREVIOUS CONVERSATION CONTEXT ===\n"
    footer = "\n=== END OF CONTEXT ===\n\n"
    context = header + "\n\n".join(context_parts) + footer

    logger.info(
        "Built context prefix: %d messages, ~%d tokens",
        len(context_parts),
        _estimate_tokens(context),
    )

    return context


async def get_conversation_context(
    db: AsyncSession,
    conversation_id: str,
) -> str:
    """Retrieve conversation history and build context prefix.

    Args:
        db: Async database session.
        conversation_id: UUID of the conversation.

    Returns:
        Formatted context string for prepending to the user query.
    """
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.step_number)
    )
    messages = list(result.scalars().all())

    return build_context_prefix(messages)
