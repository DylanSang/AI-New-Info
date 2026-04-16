from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean)


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def make_content_fingerprint(title: str, content: str) -> str:
    payload = normalize_text(f"{title} {content[:300]}")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def deduplicate(records: list[dict[str, Any]], similarity_threshold: float = 0.78) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for record in records:
        record["article_url"] = normalize_url(record["article_url"])
        if record["article_url"] in seen_urls:
            continue
        seen_urls.add(record["article_url"])
        deduped.append(record)

    final_records: list[dict[str, Any]] = []
    for rec in deduped:
        is_dup = False
        for existing in final_records:
            title_sim = _similarity(rec["title"], existing["title"])
            content_sim = _similarity(rec.get("content", ""), existing.get("content", ""))
            if (title_sim * 0.7 + content_sim * 0.3) >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            final_records.append(rec)
    return final_records


def build_event_id(record: dict[str, Any]) -> str:
    title_seed = normalize_text(record["title"])[:80]
    return hashlib.md5(title_seed.encode("utf-8")).hexdigest()


def cluster_events(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        grouped[build_event_id(rec)].append(rec)

    events: dict[str, dict[str, Any]] = {}
    for event_id, items in grouped.items():
        items_sorted = sorted(items, key=lambda x: x["published_at"])
        sources = sorted({f'{i["source_name"]} ({i["country"]})' for i in items_sorted})
        events[event_id] = {
            "event_id": event_id,
            "title": items_sorted[0]["title"],
            "category": items_sorted[0]["category"],
            "country": items_sorted[0]["country"],
            "timeline": [
                {
                    "published_at": it["published_at"],
                    "source_name": it["source_name"],
                    "article_url": it["article_url"],
                    "content": it.get("content", ""),
                }
                for it in items_sorted
            ],
            "sources": sources,
            "source_count": len(sources),
        }
    return events


def credibility_score(event: dict[str, Any]) -> float:
    # Heuristic: more independent sources means higher confidence.
    unique_sources = event.get("source_count", 1)
    timeline_len = len(event.get("timeline", []))
    base = min(70.0, unique_sources * 18.0)
    depth_bonus = min(20.0, timeline_len * 3.0)
    return round(min(100.0, base + depth_bonus + 10.0), 2)


def credibility_details(event: dict[str, Any]) -> dict[str, Any]:
    unique_sources = event.get("source_count", 1)
    timeline_len = len(event.get("timeline", []))

    source_score = min(70.0, unique_sources * 18.0)
    cross_verify_count = max(0, unique_sources - 1)
    cross_verify_score = min(20.0, cross_verify_count * 5.0)

    timestamps = [item.get("published_at", "") for item in event.get("timeline", [])]
    time_consistency = 10.0 if timestamps == sorted(timestamps) else 5.0
    depth_bonus = min(20.0, timeline_len * 3.0)

    final = round(min(100.0, source_score + depth_bonus + 10.0), 2)
    return {
        "score_total": final,
        "source_weight_score": round(source_score, 2),
        "cross_verification_count": cross_verify_count,
        "cross_verification_score": round(cross_verify_score, 2),
        "timeline_consistency_score": round(time_consistency, 2),
        "timeline_depth_bonus": round(depth_bonus, 2),
    }
