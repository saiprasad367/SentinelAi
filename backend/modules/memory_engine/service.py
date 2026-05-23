"""
SentinelAI — Memory Engine
pgvector semantic similarity search for historical incidents.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.events import EventType, event_bus
from modules.shared_models import Embedding, IncidentMemory
from shared.ai.embeddings import generate_embedding

logger = logging.getLogger("sentinel.memory.service")


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store_incident_memory(self, incident_id: UUID) -> Optional[IncidentMemory]:
        """
        When an incident is resolved, store it as a memory with embeddings.
        This becomes the knowledge base for future incident matching.
        """
        from modules.incident_engine.repository import IncidentRepository
        inc_repo = IncidentRepository(self.db)
        incident = await inc_repo.get_by_id(incident_id)
        if not incident:
            return None

        # Create the memory record
        memory = IncidentMemory(
            incident_id=incident_id,
            title=incident.title,
            description=incident.description,
            root_cause=incident.root_cause,
            resolution=incident.ai_summary,
            affected_services=incident.affected_services or [],
            tags=incident.tags or [],
            severity=incident.severity,
        )
        self.db.add(memory)
        await self.db.flush()

        # Generate and store embedding
        embed_text = self._build_embed_text(incident.title, incident.description, incident.root_cause)
        await self._store_embedding(
            entity_type="incident_memory",
            entity_id=memory.id,
            text_content=embed_text,
        )

        await event_bus.emit(
            EventType.MEMORY_STORED,
            payload={"memory_id": str(memory.id), "incident_id": str(incident_id)},
        )
        logger.info(f"Stored memory for incident {incident_id}")
        return memory

    async def search_similar(
        self,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Semantic similarity search over incident memories using pgvector.
        Falls back to JSON-stored embeddings if pgvector extension not available.
        """
        query_embedding = await generate_embedding(query)

        # Try pgvector cosine similarity search
        results = await self._vector_search(query_embedding, limit, min_similarity)

        if not results:
            # Fallback: load all embeddings and compute in Python
            results = await self._python_similarity_search(query_embedding, limit, min_similarity)

        await event_bus.emit(
            EventType.MEMORY_MATCHED,
            payload={"query": query[:100], "matches": len(results)},
        )
        return results

    async def _vector_search(
        self,
        embedding: List[float],
        limit: int,
        min_similarity: float,
    ) -> List[Dict]:
        """pgvector cosine similarity search."""
        try:
            # Use raw SQL for pgvector operations
            embed_str = json.dumps(embedding)
            sql = text("""
                SELECT
                    e.entity_id,
                    e.text_content,
                    1 - (e.embedding_json::vector <=> :query_vector::vector) as similarity
                FROM embeddings e
                WHERE e.entity_type = 'incident_memory'
                  AND 1 - (e.embedding_json::vector <=> :query_vector::vector) >= :min_sim
                ORDER BY e.embedding_json::vector <=> :query_vector::vector
                LIMIT :limit
            """)
            result = await self.db.execute(
                sql,
                {"query_vector": embed_str, "min_sim": min_similarity, "limit": limit},
            )
            rows = result.fetchall()
            return await self._hydrate_results(rows)
        except Exception as e:
            logger.warning(f"pgvector search failed, using Python fallback: {e}")
            return []

    async def _python_similarity_search(
        self,
        query_embedding: List[float],
        limit: int,
        min_similarity: float,
    ) -> List[Dict]:
        """Python cosine similarity fallback."""
        from shared.ai.embeddings import cosine_similarity

        result = await self.db.execute(
            select(Embedding).where(Embedding.entity_type == "incident_memory")
        )
        embeddings = result.scalars().all()

        scored = []
        for emb in embeddings:
            if emb.embedding_json:
                sim = cosine_similarity(query_embedding, emb.embedding_json)
                if sim >= min_similarity:
                    scored.append((emb.entity_id, emb.text_content, sim))

        scored.sort(key=lambda x: x[2], reverse=True)
        return await self._hydrate_results([(r[0], r[1], r[2]) for r in scored[:limit]])

    async def _hydrate_results(self, rows) -> List[Dict]:
        """Load full memory records for matched entity IDs."""
        results = []
        for row in rows:
            entity_id, text_content, similarity = row[0], row[1], row[2]
            mem_result = await self.db.execute(
                select(IncidentMemory).where(IncidentMemory.id == entity_id)
            )
            memory = mem_result.scalar_one_or_none()
            if memory:
                results.append({
                    "memory_id": str(memory.id),
                    "incident_id": str(memory.incident_id),
                    "title": memory.title,
                    "description": memory.description,
                    "root_cause": memory.root_cause,
                    "resolution": memory.resolution,
                    "affected_services": memory.affected_services,
                    "severity": memory.severity,
                    "similarity": round(float(similarity), 3),
                })
        return results

    async def _store_embedding(
        self,
        entity_type: str,
        entity_id: UUID,
        text_content: str,
    ) -> None:
        """Generate and store embedding for an entity."""
        try:
            embedding = await generate_embedding(text_content)
            emb = Embedding(
                entity_type=entity_type,
                entity_id=entity_id,
                text_content=text_content[:2000],
                embedding_json=embedding,
                model_name=settings.hf_embedding_model,
            )
            self.db.add(emb)
            await self.db.flush()
        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")

    def _build_embed_text(self, title: str, description: Optional[str], root_cause: Optional[str]) -> str:
        parts = [title]
        if description:
            parts.append(description[:300])
        if root_cause:
            parts.append(f"Root cause: {root_cause[:300]}")
        return " | ".join(parts)

    async def list_memories(self, limit: int = 20) -> List[IncidentMemory]:
        result = await self.db.execute(
            select(IncidentMemory).order_by(IncidentMemory.created_at.desc()).limit(limit)
        )
        return result.scalars().all()
