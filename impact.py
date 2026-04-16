from __future__ import annotations

from typing import Any


RISK_KEYWORDS = {
    "geopolitics": ["sanction", "conflict", "war", "military", "border", "nato"],
    "market": ["inflation", "interest rate", "recession", "market crash", "volatility"],
    "technology": ["ai", "chip", "cyber", "data breach", "quantum"],
    "policy": ["law", "regulation", "tariff", "ban", "election", "executive order"],
}


def _count_hits(text: str) -> int:
    raw = text.lower()
    return sum(1 for group in RISK_KEYWORDS.values() for kw in group if kw in raw)


def _range_score(event: dict[str, Any]) -> float:
    country = event.get("country", "global").lower()
    sources = event.get("source_count", 1)
    if country == "global":
        return min(30.0, 22.0 + sources * 2.0)
    return min(22.0, 12.0 + sources * 1.8)


def _intensity_score(event: dict[str, Any]) -> float:
    timeline = event.get("timeline", [])
    text = " ".join([event.get("title", "")] + [x.get("content", "") for x in timeline])
    hits = _count_hits(text)
    return min(25.0, 8.0 + hits * 2.5)


def _time_horizon_score(event: dict[str, Any]) -> float:
    # If sources keep reporting, treat as persistent signal.
    timeline_len = len(event.get("timeline", []))
    if timeline_len >= 5:
        return 18.0
    if timeline_len >= 3:
        return 13.0
    return 8.0


def _industry_score(category: str) -> float:
    mapping = {
        "technology": 15.0,
        "finance": 14.0,
        "politics": 12.0,
        "military": 15.0,
        "culture": 9.0,
        "humanities": 9.0,
    }
    return mapping.get(category.lower(), 10.0)


def evaluate_impact(event: dict[str, Any], credibility: float) -> dict[str, Any]:
    s_range = _range_score(event)
    s_intensity = _intensity_score(event)
    s_horizon = _time_horizon_score(event)
    s_industry = _industry_score(event.get("category", ""))
    s_cred = min(12.0, credibility * 0.12)

    total = round(min(100.0, s_range + s_intensity + s_horizon + s_industry + s_cred), 2)
    risk_level = "high" if total >= 75 else "medium" if total >= 45 else "low"
    return {
        "score_total": total,
        "risk_level": risk_level,
        "detail": {
            "range": round(s_range, 2),
            "intensity": round(s_intensity, 2),
            "time_horizon": round(s_horizon, 2),
            "industry": round(s_industry, 2),
            "credibility_bonus": round(s_cred, 2),
        },
    }
