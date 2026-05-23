"""SentinelAI — Chat Engine Controller"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.chat_engine.service import ChatService

router = APIRouter(prefix="/chat", tags=["AI Chat"])


class SessionCreate(BaseModel):
    incident_id: Optional[UUID] = None
    title: Optional[str] = None


class MessageCreate(BaseModel):
    content: str


@router.post("/sessions", status_code=201)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)):
    """Create a new AI chat session."""
    svc = ChatService(db)
    session = await svc.create_session(payload.incident_id, payload.title)
    return {"session_id": str(session.id), "title": session.title, "model": session.model_used}


@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all chat sessions."""
    svc = ChatService(db)
    sessions = await svc.get_sessions()
    return [
        {"id": str(s.id), "title": s.title, "incident_id": str(s.incident_id) if s.incident_id else None, "created_at": s.created_at.isoformat()}
        for s in sessions
    ]


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: UUID, payload: MessageCreate, db: AsyncSession = Depends(get_db)):
    """Send a message and get AI response (non-streaming)."""
    svc = ChatService(db)
    try:
        result = await svc.send_message(session_id, payload.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.get("/sessions/{session_id}/stream")
async def stream_chat(session_id: UUID, message: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    SSE streaming chat endpoint.
    Frontend sends message as query param, receives streamed response.
    """
    svc = ChatService(db)

    async def generate():
        async for chunk in svc.stream_response(session_id, message):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get session details with message history."""
    svc = ChatService(db)
    session = await svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": str(session.id),
        "title": session.title,
        "model": session.model_used,
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in session.messages
        ],
    }
