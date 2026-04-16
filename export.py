from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path


def export_json(conn: sqlite3.Connection, output: str) -> None:
    rows = conn.execute(
        """
        SELECT event_id, title, category, country, source_count, credibility,
               credibility_detail_json, impact_score, risk_level,
               timeline_json, sources_json
        FROM events
        ORDER BY impact_score DESC
        """
    ).fetchall()
    keys = [
        "event_id",
        "title",
        "category",
        "country",
        "source_count",
        "credibility",
        "credibility_detail",
        "impact_score",
        "risk_level",
        "timeline",
        "sources",
    ]

    data = []
    for row in rows:
        item = dict(zip(keys, row))
        item["credibility_detail"] = json.loads(item["credibility_detail"] or "{}")
        item["timeline"] = json.loads(item["timeline"] or "[]")
        item["sources"] = json.loads(item["sources"] or "[]")
        data.append(item)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_csv(conn: sqlite3.Connection, output: str) -> None:
    rows = conn.execute(
        """
        SELECT event_id, title, category, country, source_count, credibility,
               impact_score, risk_level
        FROM events
        ORDER BY impact_score DESC
        """
    ).fetchall()
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["event_id", "title", "category", "country", "source_count", "credibility", "impact_score", "risk_level"]
        )
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export events from SQLite")
    parser.add_argument("--db", default="intel.db", help="SQLite DB path")
    parser.add_argument("--format", choices=["json", "csv"], required=True, help="Export format")
    parser.add_argument("--out", required=True, help="Output file path")
    args = parser.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    try:
        if args.format == "json":
            export_json(conn, args.out)
        else:
            export_csv(conn, args.out)
    finally:
        conn.close()

    print(f"Exported {args.format} to {args.out}")


if __name__ == "__main__":
    main()
