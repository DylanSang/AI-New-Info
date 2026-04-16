from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from collector import collect_news, load_config
from impact import evaluate_impact
from processor import cluster_events, credibility_details, deduplicate
from timeline import timeline_text


DB_PATH = "intel.db"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT,
            country TEXT,
            source_count INTEGER,
            credibility REAL,
            credibility_detail_json TEXT,
            impact_score REAL,
            risk_level TEXT,
            timeline_json TEXT,
            sources_json TEXT
        )
        """
    )
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
    if "credibility_detail_json" not in existing_cols:
        conn.execute("ALTER TABLE events ADD COLUMN credibility_detail_json TEXT")
    conn.commit()


def save_events(conn: sqlite3.Connection, events: list[dict[str, Any]]) -> None:
    sql = """
    INSERT OR REPLACE INTO events (
        event_id, title, category, country, source_count, credibility,
        credibility_detail_json, impact_score, risk_level, timeline_json, sources_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with conn:
        for e in events:
            conn.execute(
                sql,
                (
                    e["event_id"],
                    e["title"],
                    e["category"],
                    e["country"],
                    e["source_count"],
                    e["credibility"],
                    json.dumps(e["credibility_detail"], ensure_ascii=False),
                    e["impact"]["score_total"],
                    e["impact"]["risk_level"],
                    json.dumps(e["timeline"], ensure_ascii=False),
                    json.dumps(e["sources"], ensure_ascii=False),
                ),
            )


def run_pipeline(config_path: str, db_path: str, print_top: int = 5) -> None:
    cfg = load_config(config_path)
    threshold = float(cfg.get("settings", {}).get("dedup_similarity_threshold", 0.78))

    raw = collect_news(config_path)
    cleaned = deduplicate(raw, similarity_threshold=threshold)
    event_map = cluster_events(cleaned)

    final_events: list[dict[str, Any]] = []
    for event in event_map.values():
        cred_detail = credibility_details(event)
        cred = cred_detail["score_total"]
        impact = evaluate_impact(event, credibility=cred)
        event["credibility"] = cred
        event["credibility_detail"] = cred_detail
        event["impact"] = impact
        final_events.append(event)

    final_events.sort(key=lambda x: x["impact"]["score_total"], reverse=True)
    conn = sqlite3.connect(db_path)
    init_db(conn)
    save_events(conn, final_events)
    conn.close()

    print(f"Pipeline completed. Raw={len(raw)}, Dedup={len(cleaned)}, Events={len(final_events)}")
    for e in final_events[:print_top]:
        print("=" * 80)
        print(f'Title: {e["title"]}')
        print(
            f'Category={e["category"]} | Country={e["country"]} | '
            f'Credibility={e["credibility"]} | Impact={e["impact"]["score_total"]} '
            f'({e["impact"]["risk_level"]})'
        )
        print(timeline_text(e))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Global intel collector MVP")
    parser.add_argument("--config", default="sources.yaml", help="Path to source config YAML")
    parser.add_argument("--db", default=DB_PATH, help="SQLite DB output path")
    parser.add_argument("--top", type=int, default=5, help="Print top N events")
    return parser.parse_args()


if __name__ == "__main__":
    setup_logging()
    args = parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    run_pipeline(config_path=args.config, db_path=args.db, print_top=args.top)
