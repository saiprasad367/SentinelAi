"""
SentinelAI — Graph Engine: BFS Blast Radius + Knowledge Graph
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.events import EventType, event_bus
from modules.shared_models import ArchitectureEdge, ArchitectureNode

logger = logging.getLogger("sentinel.graph.service")

# Default architecture seed for demo
DEFAULT_NODES = [
    {"node_id": "frontend",      "label": "Frontend",        "node_type": "frontend",  "criticality": 7},
    {"node_id": "api-gateway",   "label": "API Gateway",     "node_type": "service",   "criticality": 9},
    {"node_id": "auth-service",  "label": "Auth Service",    "node_type": "service",   "criticality": 9},
    {"node_id": "payment-api",   "label": "Payment API",     "node_type": "service",   "criticality": 10},
    {"node_id": "order-service", "label": "Order Service",   "node_type": "service",   "criticality": 8},
    {"node_id": "user-service",  "label": "User Service",    "node_type": "service",   "criticality": 7},
    {"node_id": "notification",  "label": "Notification",    "node_type": "service",   "criticality": 5},
    {"node_id": "postgres-main", "label": "PostgreSQL Main", "node_type": "database",  "criticality": 10},
    {"node_id": "redis-cache",   "label": "Redis Cache",     "node_type": "cache",     "criticality": 7},
    {"node_id": "kafka",         "label": "Kafka Queue",     "node_type": "queue",     "criticality": 6},
    {"node_id": "stripe",        "label": "Stripe",          "node_type": "external",  "criticality": 8},
    {"node_id": "sendgrid",      "label": "SendGrid",        "node_type": "external",  "criticality": 4},
]

DEFAULT_EDGES = [
    ("frontend",      "api-gateway",   "depends_on"),
    ("api-gateway",   "auth-service",  "depends_on"),
    ("api-gateway",   "payment-api",   "depends_on"),
    ("api-gateway",   "order-service", "depends_on"),
    ("api-gateway",   "user-service",  "depends_on"),
    ("payment-api",   "postgres-main", "reads_from"),
    ("payment-api",   "redis-cache",   "caches_in"),
    ("payment-api",   "stripe",        "calls"),
    ("payment-api",   "kafka",         "publishes_to"),
    ("order-service", "postgres-main", "reads_from"),
    ("order-service", "redis-cache",   "caches_in"),
    ("order-service", "kafka",         "publishes_to"),
    ("user-service",  "postgres-main", "reads_from"),
    ("auth-service",  "redis-cache",   "caches_in"),
    ("kafka",         "notification",  "triggers"),
    ("notification",  "sendgrid",      "calls"),
]


class GraphService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def seed_default_architecture(self) -> int:
        """Populate graph with default architecture if empty."""
        result = await self.db.execute(select(ArchitectureNode).limit(1))
        if result.scalar_one_or_none():
            return 0  # Already seeded

        nodes_created = 0
        for nd in DEFAULT_NODES:
            node = ArchitectureNode(**nd)
            self.db.add(node)
            nodes_created += 1

        await self.db.flush()

        for src, tgt, edge_type in DEFAULT_EDGES:
            edge = ArchitectureEdge(
                source_node_id=src,
                target_node_id=tgt,
                edge_type=edge_type,
            )
            self.db.add(edge)

        await self.db.flush()
        logger.info(f"Seeded {nodes_created} nodes and {len(DEFAULT_EDGES)} edges")
        return nodes_created

    async def get_all_nodes(self) -> List[ArchitectureNode]:
        result = await self.db.execute(select(ArchitectureNode))
        return result.scalars().all()

    async def get_all_edges(self) -> List[ArchitectureEdge]:
        result = await self.db.execute(select(ArchitectureEdge))
        return result.scalars().all()

    async def add_node(self, **kwargs) -> ArchitectureNode:
        node = ArchitectureNode(**kwargs)
        self.db.add(node)
        await self.db.flush()
        await self.db.refresh(node)
        return node

    async def add_edge(self, **kwargs) -> ArchitectureEdge:
        edge = ArchitectureEdge(**kwargs)
        self.db.add(edge)
        await self.db.flush()
        await self.db.refresh(edge)
        return edge

    async def update_node_health(self, node_id: str, health_status: str) -> Optional[ArchitectureNode]:
        result = await self.db.execute(
            select(ArchitectureNode).where(ArchitectureNode.node_id == node_id)
        )
        node = result.scalar_one_or_none()
        if node:
            old_status = node.health_status
            node.health_status = health_status
            node.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            if old_status != health_status:
                await event_bus.emit(
                    EventType.SERVICE_HEALTH_CHANGED,
                    payload={"node_id": node_id, "old": old_status, "new": health_status},
                )
        return node

    async def compute_blast_radius(self, failed_node_id: str) -> Dict[str, Any]:
        """
        BFS traversal to compute blast radius of a failing service.
        Returns direct and indirect impacted services with criticality scores.
        """
        # Build adjacency list (downstream = who depends on this node)
        all_edges = await self.get_all_edges()
        all_nodes = await self.get_all_nodes()

        # Build reverse adjacency: node -> list of nodes that depend on it
        reverse_adj: Dict[str, List[str]] = {}
        for edge in all_edges:
            if edge.target_node_id not in reverse_adj:
                reverse_adj[edge.target_node_id] = []
            reverse_adj[edge.target_node_id].append(edge.source_node_id)

        node_map = {n.node_id: n for n in all_nodes}

        # BFS
        visited: Set[str] = set()
        queue = deque([(failed_node_id, 0)])  # (node_id, depth)
        direct_impact = []
        indirect_impact = []

        while queue:
            current_id, depth = queue.popleft()
            if current_id in visited:
                continue
            visited.add(current_id)

            dependents = reverse_adj.get(current_id, [])
            for dep_id in dependents:
                if dep_id not in visited:
                    if depth == 0:
                        direct_impact.append(dep_id)
                    else:
                        indirect_impact.append(dep_id)
                    queue.append((dep_id, depth + 1))

        # Compute criticality score
        total_criticality = sum(
            node_map[n].criticality for n in (direct_impact + indirect_impact)
            if n in node_map
        )
        max_possible = sum(n.criticality for n in all_nodes)
        criticality_score = (total_criticality / max_possible * 100) if max_possible > 0 else 0

        result = {
            "failed_service": failed_node_id,
            "direct_impact": direct_impact,
            "indirect_impact": indirect_impact,
            "impacted_services": list(set(direct_impact + indirect_impact)),
            "total_impacted_count": len(set(direct_impact + indirect_impact)),
            "criticality_score": round(criticality_score, 1),
        }

        await event_bus.emit(
            EventType.BLAST_RADIUS_COMPUTED,
            payload=result,
        )
        return result

    async def check_and_emit_health_changes(self) -> None:
        """Called by scheduler to check node health and emit events."""
        # In real deployment: query actual services
        # For hackathon: no-op (health changes triggered by incident events)
        pass

    async def get_full_graph(self) -> Dict:
        """Return complete graph structure for frontend visualization."""
        nodes = await self.get_all_nodes()
        edges = await self.get_all_edges()
        return {
            "nodes": [
                {
                    "id": n.node_id,
                    "label": n.label,
                    "type": n.node_type,
                    "health": n.health_status,
                    "criticality": n.criticality,
                    "x": n.position_x,
                    "y": n.position_y,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "source": e.source_node_id,
                    "target": e.target_node_id,
                    "type": e.edge_type,
                    "weight": e.weight,
                }
                for e in edges
            ],
        }
