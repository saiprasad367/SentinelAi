"""
SentinelAI — Graph Engine Controller
/api/v1/graph - nodes, edges, blast radius
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.graph_engine.service import GraphService

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


class NodeCreate(BaseModel):
    node_id: str
    label: str
    node_type: str = "service"
    criticality: int = 5
    position_x: Optional[float] = None
    position_y: Optional[float] = None


class EdgeCreate(BaseModel):
    source_node_id: str
    target_node_id: str
    edge_type: str = "depends_on"
    weight: float = 1.0


@router.get("/")
async def get_full_graph(db: AsyncSession = Depends(get_db)):
    """Get full architecture graph for frontend visualization."""
    svc = GraphService(db)
    await svc.seed_default_architecture()
    return await svc.get_full_graph()


@router.get("/nodes")
async def get_nodes(db: AsyncSession = Depends(get_db)):
    """List all architecture nodes."""
    svc = GraphService(db)
    await svc.seed_default_architecture()
    nodes = await svc.get_all_nodes()
    return [{"id": n.node_id, "label": n.label, "type": n.node_type, "health": n.health_status, "criticality": n.criticality} for n in nodes]


@router.post("/nodes", status_code=201)
async def add_node(payload: NodeCreate, db: AsyncSession = Depends(get_db)):
    """Add a new node to the architecture graph."""
    svc = GraphService(db)
    node = await svc.add_node(**payload.model_dump())
    return {"id": node.node_id, "label": node.label, "status": "created"}


@router.get("/edges")
async def get_edges(db: AsyncSession = Depends(get_db)):
    """List all architecture edges."""
    svc = GraphService(db)
    edges = await svc.get_all_edges()
    return [{"source": e.source_node_id, "target": e.target_node_id, "type": e.edge_type} for e in edges]


@router.post("/edges", status_code=201)
async def add_edge(payload: EdgeCreate, db: AsyncSession = Depends(get_db)):
    """Add a new dependency edge."""
    svc = GraphService(db)
    edge = await svc.add_edge(**payload.model_dump())
    return {"id": str(edge.id), "status": "created"}


@router.get("/blast-radius/{node_id}")
async def compute_blast_radius(node_id: str, db: AsyncSession = Depends(get_db)):
    """
    Compute blast radius of a failing service using BFS traversal.
    Returns direct + indirect impacted services and criticality score.
    """
    svc = GraphService(db)
    await svc.seed_default_architecture()
    result = await svc.compute_blast_radius(node_id)
    return result


@router.patch("/nodes/{node_id}/health")
async def update_node_health(node_id: str, health_status: str, db: AsyncSession = Depends(get_db)):
    """Update service health status."""
    valid = {"healthy", "degraded", "down"}
    if health_status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid health_status. Must be one of: {valid}")
    svc = GraphService(db)
    node = await svc.update_node_health(node_id, health_status)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return {"node_id": node_id, "health_status": health_status}
