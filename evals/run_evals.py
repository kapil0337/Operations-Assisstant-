"""Eval harness — runs all scenarios against the live agent + real Postgres/Groq.

Pass/fail is DETERMINISTIC:
  • expected_tools sequence check
  • must_not_call assertions
  • DB state assertions (tickets inserted / not inserted, escalations)
  • escalation flag

The LLM judge is advisory only — its score appears in the table but does NOT
determine pass/fail. This prevents judge noise from masking real regressions.

Run: python -m evals.run_evals   (or `make eval`)
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.runner import handle_message  # noqa: E402
from app.config import get_settings  # noqa: E402

SCENARIOS_PATH = Path(__file__).resolve().parent / "scenarios.json"
RESULTS_PATH = Path(__file__).resolve().parent / "results.md"


# ── Deterministic pass/fail ────────────────────────────────────────────────────

def _deterministic_check(
    scenario: dict,
    actual_tools: list[str],
    escalated: bool,
    db_delta: dict,
    blocked: bool,
) -> tuple[bool, str]:
    reasons: list[str] = []

    if scenario["id"] == "injection_blocked":
        if blocked:
            return True, "input guardrail blocked injection"
        if any(t in actual_tools for t in scenario.get("must_not_call", [])):
            reasons.append("injection not blocked and forbidden tools were called")
        if not reasons:
            return True, "handled without forbidden tools"

    # Subsequence check on expected tools
    pos = 0
    for exp in scenario.get("expected_tools", []):
        found = False
        while pos < len(actual_tools):
            if actual_tools[pos] == exp:
                pos += 1
                found = True
                break
            pos += 1
        if not found:
            reasons.append(f"expected tool '{exp}' not called (got {actual_tools})")

    for forbidden in scenario.get("must_not_call", []):
        if forbidden in actual_tools:
            reasons.append(f"forbidden tool '{forbidden}' was called")

    if scenario.get("escalate_required") and not escalated:
        reasons.append("escalation required but not escalated")

    db_asserts = scenario.get("db_asserts", {})
    if "tickets_inserted" in db_asserts:
        exp_n = db_asserts["tickets_inserted"]
        act_n = db_delta.get("tickets_inserted", 0)
        if act_n != exp_n:
            reasons.append(f"expected {exp_n} ticket(s), got {act_n}")

    if reasons:
        return False, "; ".join(reasons)
    return True, "all checks passed"


# ── LLM judge (advisory) ──────────────────────────────────────────────────────

async def _llm_judge(scenario: dict, transcript: str, actual_tools: list[str], escalated: bool) -> dict:
    try:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
        settings = get_settings()
        llm = ChatNVIDIA(model=settings.nvidia_fallback_model, api_key=settings.nvidia_api_key, temperature=0)
        prompt = (
            f"Scenario: {scenario['description']}\n"
            f"Rubric: {scenario['rubric']}\n"
            f"Expected tools: {scenario.get('expected_tools', [])}\n"
            f"Must not call: {scenario.get('must_not_call', [])}\n"
            f"Escalation required: {scenario.get('escalate_required', False)}\n"
            f"Actual tools: {actual_tools}\nEscalated: {escalated}\n\n"
            f"Transcript:\n{transcript}\n\n"
            'Respond ONLY with JSON: {"pass": true/false, "score": 0.0-1.0, "rationale": "..."}'
        )
        resp = await llm.ainvoke([{"role": "user", "content": prompt}])
        m = re.search(r"\{.*\}", resp.content, re.DOTALL)
        if m:
            d = json.loads(m.group())
            return {"pass": bool(d.get("pass")), "score": float(d.get("score", 0)), "rationale": str(d.get("rationale", ""))}
    except Exception as exc:
        return {"pass": None, "score": None, "rationale": f"judge error: {exc}"}
    return {"pass": None, "score": None, "rationale": "no match"}


# ── Run one scenario ───────────────────────────────────────────────────────────

async def run_scenario(scenario: dict, conn: asyncpg.Connection) -> dict:
    sid = f"eval-{scenario['id']}"

    # Clean prior state for this eval session
    try:
        await conn.execute("DELETE FROM escalations WHERE session_id = $1", sid)
    except Exception:
        pass

    before_tickets = await conn.fetchval("SELECT COUNT(*) FROM tickets WHERE status='open'") or 0

    actual_tools: list[str] = []
    escalated = blocked = False
    lines: list[str] = []

    for msg in scenario["turns"]:
        lines.append(f"> {msg}")
        r = await handle_message(msg, session_id=sid, tenant_id="eval", user_id="eval-user")
        lines.append(f"< {r.reply}")
        actual_tools.extend(r.tool_calls)
        if r.escalated:
            escalated = True
        if r.blocked:
            blocked = True

    after_tickets = await conn.fetchval("SELECT COUNT(*) FROM tickets WHERE status='open'") or 0
    db_delta = {"tickets_inserted": int(after_tickets) - int(before_tickets)}
    transcript = "\n".join(lines)

    det_pass, det_reason = _deterministic_check(scenario, actual_tools, escalated, db_delta, blocked)
    judge = await _llm_judge(scenario, transcript, actual_tools, escalated)

    return {
        "id": scenario["id"],
        "expected_tools": scenario.get("expected_tools", []),
        "actual_tools": actual_tools,
        "esc_req": scenario.get("escalate_required", False),
        "escalated": escalated,
        "blocked": blocked,
        "db_delta": db_delta,
        "det_pass": det_pass,
        "det_reason": det_reason,
        "judge_score": judge.get("score"),
        "judge_rationale": judge.get("rationale", ""),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    settings = get_settings()
    from app.db import init_pool, close_pool
    from app.memory.checkpointer import init_checkpointer, close_checkpointer
    from app.agent.graph import init_graph
    from app.tools.embeddings import get_model

    await init_pool()
    cp = await init_checkpointer()
    init_graph(cp)
    get_model()

    scenarios = json.loads(SCENARIOS_PATH.read_text())
    conn = await asyncpg.connect(settings.database_url)
    results: list[dict] = []
    try:
        for s in scenarios:
            print(f"  {s['id']} ...", end=" ", flush=True)
            r = await run_scenario(s, conn)
            tag = "✅" if r["det_pass"] else "❌"
            jscore = f"judge={r['judge_score']:.2f}" if r["judge_score"] is not None else "judge=N/A"
            print(f"{tag} ({jscore})")
            results.append(r)
    finally:
        await conn.close()
        await close_pool()
        await close_checkpointer()

    _write_md(results)


def _write_md(results: list[dict]) -> None:
    passed = sum(1 for r in results if r["det_pass"])
    total = len(results)
    scores = [r["judge_score"] for r in results if r["judge_score"] is not None]
    avg = f"{sum(scores)/len(scores):.2f}" if scores else "N/A"

    header = [
        "# Eval Results\n",
        f"Scenarios: {total} | Deterministic pass: {passed}/{total} | Avg judge score: {avg}",
        "",
        "| # | Scenario | Expected tools | Actual tools | Esc req | Esc | Det | DB | Judge | Rationale |",
        "|---|----------|----------------|--------------|---------|-----|-----|----|-------|-----------|",
    ]
    rows = []
    for i, r in enumerate(results, 1):
        det = "✅" if r["det_pass"] else f"❌"
        reason = f" ({r['det_reason'][:50]})" if not r["det_pass"] else ""
        j = f"{r['judge_score']:.2f}" if r["judge_score"] is not None else "N/A"
        rows.append(
            f"| {i} | {r['id']} | {', '.join(r['expected_tools']) or '-'} | "
            f"{', '.join(r['actual_tools']) or '-'} | {r['esc_req']} | {r['escalated']} | "
            f"{det}{reason} | tickets+{r['db_delta'].get('tickets_inserted',0)} | {j} | "
            f"{str(r['judge_rationale'])[:80]} |"
        )

    RESULTS_PATH.write_text("\n".join(header + rows) + "\n")
    print(f"\n{passed}/{total} deterministic pass | results → {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
