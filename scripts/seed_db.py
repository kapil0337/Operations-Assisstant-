"""Seeds sample orders/tickets and embeds the KB corpus.

Schema is now managed by Alembic (run `alembic upgrade head` first).
This script only inserts/refreshes data.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.tools.embeddings import embed_text  # noqa: E402

KB_DIR = Path(__file__).resolve().parent / "kb"

ORDERS = [
    # order_id, customer_email, item, amount_cents, status, charge_count, days_ago
    (1042, "alex@example.com", "Wireless Mouse", 2999, "processing", 2, 2),
    (2001, "jordan@example.com", "USB-C Cable", 1299, "shipped", 1, 3),
    (3050, "sam@example.com", "Bluetooth Speaker", 5999, "refunded", 1, 20),
    (4090, "riley@example.com", "Mechanical Keyboard", 8999, "delivered", 1, 5),
    (5500, "casey@example.com", "Office Chair", 18999, "delayed", 1, 25),
]

TICKETS = [
    # order_id, type, status, reason
    (3050, "refund", "closed", "customer requested refund - approved and processed"),
]


def _vec(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


def _chunk_markdown(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


async def seed(conn: asyncpg.Connection) -> None:
    # Clear mutable data; keep schema (managed by alembic)
    await conn.execute("TRUNCATE tickets, escalations, kb_chunks RESTART IDENTITY CASCADE")
    await conn.execute("DELETE FROM orders")

    for order_id, email, item, amount, status, charge_count, days_ago in ORDERS:
        await conn.execute(
            """
            INSERT INTO orders (order_id, customer_email, item, amount_cents, status, charge_count, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, now() - ($7 * INTERVAL '1 day'))
            """,
            order_id, email, item, amount, status, charge_count, days_ago,
        )

    for order_id, ttype, tstatus, reason in TICKETS:
        await conn.execute(
            "INSERT INTO tickets (order_id, type, status, reason) VALUES ($1, $2, $3, $4)",
            order_id, ttype, tstatus, reason,
        )

    for path in sorted(KB_DIR.glob("*.md")):
        for chunk in _chunk_markdown(path.read_text(encoding="utf-8")):
            vector = embed_text(chunk)
            await conn.execute(
                "INSERT INTO kb_chunks (source, content, embedding) VALUES ($1, $2, $3::vector)",
                path.name, chunk, _vec(vector),
            )

    print(f"Seeded {len(ORDERS)} orders, {len(TICKETS)} tickets, KB from {KB_DIR}")


async def main() -> None:
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        await seed(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
