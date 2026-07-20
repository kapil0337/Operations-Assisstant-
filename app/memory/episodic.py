"""Episodic memory: store + recall resolved support episodes.

Each episode captures the problem summary, the resolution, which tools were
used, and the outcome.  At plan time the supervisor retrieves the K most
similar past episodes so it can apply institutional knowledge without
hallucinating — e.g. "last time a customer disputed a charge on a refunded
order, we escalated rather than issuing a second refund."
"""
from __future__ import annotations

from app.db import get_pool
from app.tools import embeddings


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in v) + "]"


async def recall_similar_episodes(
    tenant_id: str, query: str, k: int = 3
) -> list[dict]:
    """Return up to k past episodes whose problem-embedding is nearest to query."""
    try:
        emb = embeddings.embed_text(query)
    except Exception:
        return []
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT problem, resolution, tools_used, outcome,
               1 - (embedding <=> $2::vector) AS similarity
        FROM episodes
        WHERE tenant_id = $1
        ORDER BY embedding <=> $2::vector
        LIMIT $3
        """,
        tenant_id, _vec(emb), k,
    )
    return [dict(r) for r in rows]


async def store_episode(
    tenant_id: str,
    session_id: str,
    problem: str,
    resolution: str,
    tools_used: list[str],
    outcome: str,
) -> None:
    try:
        emb = embeddings.embed_text(problem)
    except Exception:
        return
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO episodes (tenant_id, session_id, problem, resolution, tools_used, outcome, embedding)
        VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
        """,
        tenant_id, session_id, problem, resolution, tools_used, outcome, _vec(emb),
    )
