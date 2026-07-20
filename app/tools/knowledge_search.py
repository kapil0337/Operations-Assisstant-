"""RAG tool: semantic search over the policy/KB corpus stored in pgvector."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.db import get_pool
from app.tools import embeddings
from app.tools.base import ToolError
from langchain_core.tools import tool


class KnowledgeSearchInput(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural-language question to search the KB for.")
    top_k: int = Field(default=3, ge=1, le=10)


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


@tool("knowledge_search", args_schema=KnowledgeSearchInput)
async def knowledge_search(query: str, top_k: int = 3) -> dict:
    """Search internal policy/KB documents (refunds, shipping, escalation rules, etc.)
    for passages relevant to the user's question. Always prefer this over guessing
    at policy."""
    try:
        embedding = embeddings.embed_text(query)
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f"embedding failed: {exc}") from exc

    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT source, content, 1 - (embedding <=> $1::vector) AS score
        FROM kb_chunks
        ORDER BY embedding <=> $1::vector
        LIMIT $2
        """,
        _vector_literal(embedding),
        top_k,
    )
    results = [
        {"source": r["source"], "content": r["content"], "score": round(float(r["score"]), 4)}
        for r in rows
    ]
    return {"query": query, "results": results}
