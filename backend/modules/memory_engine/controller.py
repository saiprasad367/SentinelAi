"""
SentinelAI — Memory Engine Controller
/api/v1/memory - semantic search + storage
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.memory_engine.service import MemoryService

router = APIRouter(prefix="/memory", tags=["AI Memory"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    min_similarity: float = 0.3


@router.post("/search")
async def search_similar_incidents(
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic search over resolved incident memories.
    Returns similar incidents with confidence scores.
    """
    svc = MemoryService(db)
    results = await svc.search_similar(
        payload.query,
        limit=payload.limit,
        min_similarity=payload.min_similarity,
    )
    return {"query": payload.query, "matches": len(results), "results": results}


@router.post("/store/{incident_id}", status_code=201)
async def store_incident_memory(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Store a resolved incident as a memory with semantic embeddings.
    Call this when incident is resolved to build the knowledge base.
    """
    svc = MemoryService(db)
    memory = await svc.store_incident_memory(incident_id)
    if not memory:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return {
        "memory_id": str(memory.id),
        "incident_id": str(incident_id),
        "title": memory.title,
        "status": "stored",
    }


@router.get("/")
async def list_memories(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all stored incident memories."""
    svc = MemoryService(db)
    memories = await svc.list_memories(limit)
    return [
        {
            "id": str(m.id),
            "incident_id": str(m.incident_id),
            "title": m.title,
            "severity": m.severity,
            "root_cause": m.root_cause,
            "affected_services": m.affected_services,
            "created_at": m.created_at.isoformat(),
        }
        for m in memories
    ]
