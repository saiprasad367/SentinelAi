"""
SentinelAI — Chat Engine with RAG
AI chat grounded in incidents, graph, memories, predictions.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.shared_models import ChatMessage, ChatSession

logger = logging.getLogger("sentinel.chat.service")

CHAT_SYSTEM_PROMPT = """You are SentinelAI, an expert autonomous Site Reliability Engineer.
You have access to real-time incident data, service dependency graphs, historical incidents, and prediction models.

When answering:
- Always cite specific data from the context provided
- Express confidence levels
- Provide actionable recommendations
- Use technical SRE language
- Format responses with clear structure (use markdown)

Context is injected at the start of each user message."""


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        incident_id: Optional[UUID] = None,
        title: Optional[str] = None,
    ) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            incident_id=incident_id,
            title=title or "New Chat",
            model_used=settings.openrouter_default_model,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def send_message(
        self,
        session_id: UUID,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Send a message and get AI response.
        Injects relevant context (RAG) from incidents, graph, memories.
        """
        from shared.ai.openrouter import get_openrouter
        ai = get_openrouter()

        session = await self.db.get(ChatSession, session_id)
        if not session:
            raise ValueError(f"Chat session {session_id} not found")

        # Get conversation history
        history = await self._get_history(session_id)

        # Build context
        context = await self._build_rag_context(user_message, session.incident_id)

        # Augment user message with context
        augmented_message = f"""CONTEXT:
{context}

USER QUESTION: {user_message}"""

        # Build messages for AI
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in history[-10:]  # Last 10 messages for context window
        ]
        messages.append({"role": "user", "content": augmented_message})

        # Store user message
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=user_message,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # Get AI response
        try:
            response_text = await ai.complete(
                messages=messages,
                system_prompt=CHAT_SYSTEM_PROMPT,
                model=settings.openrouter_default_model,
                max_tokens=1500,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"AI chat failed: {e}")
            response_text = f"I'm having trouble connecting to the AI engine. Error: {str(e)[:100]}"

        # Store assistant message
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=response_text,
            citations=await self._extract_citations(context),
        )
        self.db.add(assistant_msg)
        await self.db.flush()

        return {
            "session_id": str(session_id),
            "message_id": str(assistant_msg.id),
            "response": response_text,
            "citations": assistant_msg.citations,
        }

    async def stream_response(
        self,
        session_id: UUID,
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat response via SSE."""
        from shared.ai.openrouter import get_openrouter
        from core.database import get_db_context

        ai = get_openrouter()

        async with get_db_context() as db:
            session = await db.get(ChatSession, session_id)
            if not session:
                yield 'data: {"error": "Session not found"}\n\n'
                return

            history = await self._get_history_with_db(session_id, db)
            context = await self._build_rag_context(user_message, session.incident_id)

            augmented = f"CONTEXT:\n{context}\n\nUSER QUESTION: {user_message}"
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in history[-8:]
            ]
            messages.append({"role": "user", "content": augmented})

            # Store user message
            user_msg = ChatMessage(session_id=session_id, role="user", content=user_message)
            db.add(user_msg)
            await db.flush()
            await db.commit()

            # Stream response
            full_response = ""
            try:
                async for chunk in ai.stream(
                    messages=messages,
                    system_prompt=CHAT_SYSTEM_PROMPT,
                    max_tokens=1500,
                ):
                    full_response += chunk
                    yield f'data: {json.dumps({"type": "chunk", "content": chunk})}\n\n'
            except Exception as e:
                error_msg = f"AI stream error: {str(e)[:100]}"
                yield f'data: {json.dumps({"type": "error", "message": error_msg})}\n\n'
                full_response = error_msg

            # Store assistant response
            async with get_db_context() as save_db:
                assistant_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                )
                save_db.add(assistant_msg)
                await save_db.commit()

            yield f'data: {json.dumps({"type": "done", "session_id": str(session_id)})}\n\n'

    async def _build_rag_context(
        self,
        query: str,
        incident_id: Optional[UUID] = None,
    ) -> str:
        """Build RAG context from all available sources."""
        context_parts = []

        # ── Active incidents ───────────────────────────────────────────────────
        try:
            from modules.incident_engine.repository import IncidentRepository
            inc_repo = IncidentRepository(self.db)
            recent = await inc_repo.get_recent(limit=3)
            if recent:
                context_parts.append("ACTIVE INCIDENTS:")
                for inc in recent:
                    context_parts.append(
                        f"  - [{inc.severity}] {inc.title} (status: {inc.status})"
                        + (f", root_cause: {inc.root_cause[:100]}" if inc.root_cause else "")
                    )
        except Exception as e:
            logger.debug(f"Context: incidents fetch failed: {e}")

        # ── Specific incident context ──────────────────────────────────────────
        if incident_id:
            try:
                from modules.incident_engine.repository import IncidentRepository
                inc_repo = IncidentRepository(self.db)
                inc = await inc_repo.get_by_id(incident_id)
                if inc:
                    context_parts.append(f"\nCURRENT INCIDENT: {inc.title}")
                    context_parts.append(f"  Severity: {inc.severity}, Status: {inc.status}")
                    context_parts.append(f"  Service: {inc.affected_service or 'Unknown'}")
                    if inc.root_cause:
                        context_parts.append(f"  Root Cause: {inc.root_cause[:200]}")
            except Exception:
                pass

        # ── Similar historical incidents ───────────────────────────────────────
        try:
            from modules.memory_engine.service import MemoryService
            mem_svc = MemoryService(self.db)
            similar = await mem_svc.search_similar(query, limit=2, min_similarity=0.4)
            if similar:
                context_parts.append("\nSIMILAR HISTORICAL INCIDENTS:")
                for s in similar:
                    context_parts.append(
                        f"  - {s['title']} (similarity: {s['similarity']:.0%})"
                        + (f", resolution: {s['resolution'][:100]}" if s.get('resolution') else "")
                    )
        except Exception as e:
            logger.debug(f"Context: memory search failed: {e}")

        # ── Latest predictions ─────────────────────────────────────────────────
        try:
            from modules.prediction_engine.service import PredictionService
            pred_svc = PredictionService(self.db)
            preds = await pred_svc.get_latest_predictions(limit=3)
            high_risk = [p for p in preds if p.outage_probability > 0.6]
            if high_risk:
                context_parts.append("\nHIGH-RISK PREDICTIONS:")
                for p in high_risk:
                    context_parts.append(
                        f"  - {p.service_name}/{p.metric_name}: {p.outage_probability:.0%} outage probability"
                    )
        except Exception as e:
            logger.debug(f"Context: predictions fetch failed: {e}")

        return "\n".join(context_parts) if context_parts else "No additional context available."

    async def _get_history(self, session_id: UUID) -> List[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .limit(20)
        )
        return result.scalars().all()

    async def _get_history_with_db(self, session_id: UUID, db: AsyncSession) -> List[ChatMessage]:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .limit(20)
        )
        return result.scalars().all()

    async def _extract_citations(self, context: str) -> List[str]:
        """Extract data source citations from context."""
        citations = []
        if "ACTIVE INCIDENTS:" in context:
            citations.append("Active Incidents DB")
        if "HISTORICAL INCIDENTS:" in context:
            citations.append("Incident Memory Bank")
        if "PREDICTIONS:" in context:
            citations.append("Prediction Engine")
        return citations

    async def get_session(self, session_id: UUID) -> Optional[ChatSession]:
        return await self.db.get(ChatSession, session_id)

    async def get_sessions(self, limit: int = 20) -> List[ChatSession]:
        result = await self.db.execute(
            select(ChatSession).order_by(desc(ChatSession.updated_at)).limit(limit)
        )
        return result.scalars().all()
