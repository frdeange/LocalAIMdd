"""
Conversation Routes
===================
CRUD endpoints for managing conversations.

Endpoints:
    POST   /api/conversations           — Create a new conversation
    GET    /api/conversations           — List all conversations
    GET    /api/conversations/{id}      — Get a conversation with messages
    DELETE /api/conversations/{id}      — Delete a conversation
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.database import get_db
from api.models.orm import Conversation, Message
from api.models.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation."""
    conversation = Conversation(title=body.title)
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation, attribute_names=["messages"])
    logger.info("Created conversation: %s", conversation.id)
    return conversation


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    """List all conversations, newest first, with message count."""
    # Subquery for message count
    msg_count = (
        select(Message.conversation_id, func.count(Message.id).label("message_count"))
        .group_by(Message.conversation_id)
        .subquery()
    )

    result = await db.execute(
        select(
            Conversation,
            func.coalesce(msg_count.c.message_count, 0).label("message_count"),
        )
        .outerjoin(msg_count, Conversation.id == msg_count.c.conversation_id)
        .order_by(Conversation.updated_at.desc())
    )

    conversations = []
    for row in result.all():
        conv = row[0]
        count = row[1]
        conversations.append(
            ConversationSummary(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=count,
            )
        )
    return conversations


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation with all its messages."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conversation)
    logger.info("Deleted conversation: %s", conversation_id)
