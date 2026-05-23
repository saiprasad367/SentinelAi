"""
SentinelAI — HuggingFace Embeddings
Generates semantic embeddings using BAAI/bge-small-en-v1.5.
Stored as pgvector vectors in PostgreSQL.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from core.config import settings

logger = logging.getLogger("sentinel.ai.embeddings")

_model = None


def _load_model():
    """Lazy-load the sentence transformer model (heavy, load once)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {settings.hf_embedding_model}")
        _model = SentenceTransformer(
            settings.hf_embedding_model,
            device=settings.hf_device,
        )
        logger.info("Embedding model loaded successfully")
    return _model


async def generate_embedding(text: str) -> List[float]:
    """
    Generate a semantic embedding for the given text.
    Returns a list of floats suitable for pgvector storage.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    # Run in thread pool to avoid blocking the event loop
    embedding = await loop.run_in_executor(None, _embed_sync, text)
    return embedding


def _embed_sync(text: str) -> List[float]:
    """Synchronous embedding generation (run in executor)."""
    model = _load_model()
    # Normalize text for BGE model
    instruction = f"Represent this incident for similarity search: {text}"
    embedding = model.encode(instruction, normalize_embeddings=True)
    return embedding.tolist()


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Batch embed multiple texts efficiently."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _embed_batch_sync, texts)


def _embed_batch_sync(texts: List[str]) -> List[List[float]]:
    model = _load_model()
    instructions = [f"Represent this incident for similarity search: {t}" for t in texts]
    embeddings = model.encode(instructions, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))
