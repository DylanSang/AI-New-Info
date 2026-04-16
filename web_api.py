from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import FastAPI, Query


app = FastAPI(title="Global Intel API", version="0.1.0")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect("intel.db")
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "title": row["title"],
        "category": row["category"],
        "country": row["country"],
        "source_count": row["source_count"],
        "credibility": row["credibility"],
        "credibility_detail": json.loads(row["credibility_detail_json"] or "{}"),
        "impact_score": row["impact_score"],
        "risk_level": row["risk_level"],
        "timeline": json.loads(row["timeline_json"] or "[]"),
        "sources": json.loads(row["sources_json"] or "[]"),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/events")
def events(
    limit: int = Query(50, ge=1, le=500),
    category: str | None = None,
    country: str | None = None,
    min_score: float | None = Query(None, ge=0, le=100),
) -> dict[str, Any]:
    clauses = []
    args: list[Any] = []
    if category:
        clauses.append("category = ?")
        args.append(category)
    if country:
        clauses.append("country = ?")
        args.append(country)
    if min_score is not None:
        clauses.append("impact_score >= ?")
        args.append(min_score)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
    SELECT * FROM events
    {where}
    ORDER BY impact_score DESC
    LIMIT ?
    """
    args.append(limit)

    conn = _conn()
    try:
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    return {"items": [_row_to_event(r) for r in rows], "count": len(rows)}


@app.get("/events/{event_id}")
def event_detail(event_id: str) -> dict[str, Any]:
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
    finally:
        conn.close()

    if row is None:
        return {"error": "not_found", "event_id": event_id}
    return _row_to_event(row)
