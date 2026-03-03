"""
Message Routes
==============
SSE streaming endpoint for sending messages and receiving agent responses.

Endpoint:
    POST /api/conversations/{id}/messages — Send a message, receive SSE stream
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import get_db, get_session_factory
from api.models.orm import Conversation, Message
from api.models.schemas import MessageCreate
from api.services.session import get_conversation_context
from api.services.workflow import run_workflow_sse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: MessageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and stream agent responses via SSE.

    The endpoint:
    1. Validates the conversation exists
    2. Saves the user message to the database
    3. Builds multi-turn context from conversation history
    4. Runs the MAF SequentialBuilder workflow
    5. Streams agent events as SSE
    6. Saves agent responses to the database

    Returns:
        StreamingResponse with content-type text/event-stream
    """
    # Validate conversation exists
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Save user message
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        author_name="User",
        content=body.content,
        step_number=0,
    )
    db.add(user_message)
    await db.flush()

    # Build context from history
    context_prefix = await get_conversation_context(db, conversation_id)
    full_query = context_prefix + body.content

    # Update conversation title from first message
    if conversation.title == "New Conversation":
        # Use first ~50 chars of the message as title
        conversation.title = body.content[:50].strip()
        if len(body.content) > 50:
            conversation.title += "..."

    # Commit user message before streaming
    await db.commit()

    # Get client from app state
    client = request.app.state.client
    mcp_server_url = request.app.state.mcp_server_url

    # Create the SSE generator that also persists agent responses
    async def event_stream():
        session_factory = get_session_factory()

        async for sse_event in run_workflow_sse(client, mcp_server_url, full_query):
            yield sse_event

            # Parse the event to save agent responses
            try:
                # Extract event type and data from SSE format
                lines = sse_event.strip().split("\n")
                event_type = ""
                event_data = ""
                for line in lines:
                    if line.startswith("event: "):
                        event_type = line[7:]
                    elif line.startswith("data: "):
                        event_data = line[6:]

                if event_type == "agent_completed" and event_data:
                    data = json.loads(event_data)
                    output = data.get("output", "")
                    # Only persist non-empty agent responses
                    if output and output.strip():
                        async with session_factory() as save_db:
                            agent_message = Message(
                                conversation_id=conversation_id,
                                role="assistant",
                                author_name=data.get("agent", "Agent"),
                                content=output,
                                step_number=data.get("step", 0),
                            )
                            save_db.add(agent_message)
                            await save_db.commit()

                elif event_type == "workflow_completed" and event_data:
                    # Update conversation timestamp
                    async with session_factory() as save_db:
                        result = await save_db.execute(
                            select(Conversation).where(Conversation.id == conversation_id)
                        )
                        conv = result.scalar_one_or_none()
                        if conv:
                            conv.updated_at = datetime.now(timezone.utc)
                            await save_db.commit()

            except Exception as e:
                logger.warning("Failed to persist agent event: %s", e)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
