"""Long-term per-(tenant, user) semantic fact store backed by pgvector.

Facts are short declarative sentences the agent (or a human admin) has
committed about a specific user: preferred language, known past issues,
VIP status, etc.  On every new session the most relevant facts (by cosine
similarity to the opening message) are injected into the supervisor prompt.
"""
from __future__ import annotations

from app.db import get_pool
from app.tools import embeddings


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in v) + "]"


async def recall_user_facts(tenant_id: str, user_id: str, query: str, k: int = 5) -> list[str]:
    """Return up to k fact strings most similar to `query`."""
    try:
        emb = embeddings.embed_text(query)
    except Exception:
        return []
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT fact FROM user_facts
        WHERE tenant_id = $1 AND user_id = $2
        ORDER BY embedding <=> $3::vector
        LIMIT $4
        """,
        tenant_id, user_id, _vec(emb), k,
    )
    return [r["fact"] for r in rows]


async def store_user_fact(tenant_id: str, user_id: str, fact: str) -> None:
    emb = embeddings.embed_text(fact)
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO user_facts (tenant_id, user_id, fact, embedding)
        VALUES ($1, $2, $3, $4::vector)
        ON CONFLICT DO NOTHING
        """,
        tenant_id, user_id, fact, _vec(emb),
    )
