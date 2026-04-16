from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dt_parser


logger = logging.getLogger(__name__)


@dataclass
class Source:
    name: str
    type: str
    category: str
    country: str
    language: str
    url: str


def load_config(path: str = "sources.yaml") -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _to_iso8601(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = dt_parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _strip_html(raw: str | None) -> str:
    if not raw:
        return ""
    return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)


def _fetch_rss(source: Source, timeout: int, user_agent: str) -> list[dict[str, Any]]:
    headers = {"User-Agent": user_agent}
    response = requests.get(source.url, timeout=timeout, headers=headers)
    response.raise_for_status()

    parsed = feedparser.parse(response.content)
    records: list[dict[str, Any]] = []
    for item in parsed.entries:
        title = (item.get("title") or "").strip()
        if not title:
            continue

        summary = _strip_html(item.get("summary") or item.get("description") or "")
        records.append(
            {
                "title": title,
                "published_at": _to_iso8601(item.get("published") or item.get("updated")),
                "source_name": source.name,
                "source_url": source.url,
                "article_url": item.get("link") or source.url,
                "category": source.category,
                "country": source.country,
                "language": source.language,
                "content": summary,
            }
        )
    return records


def collect_news(config_path: str = "sources.yaml") -> list[dict[str, Any]]:
    config = load_config(config_path)
    raw_sources = config.get("sources", [])
    settings = config.get("settings", {})
    timeout = int(settings.get("request_timeout_seconds", 15))
    retries = int(settings.get("max_retries", 2))
    user_agent = settings.get("user_agent", "GlobalIntelBot/0.1")

    all_records: list[dict[str, Any]] = []
    for raw in raw_sources:
        source = Source(**raw)
        if source.type != "rss":
            logger.warning("Skip unsupported source type: %s", source.type)
            continue

        last_error: Exception | None = None
        for attempt in range(1, retries + 2):
            try:
                logger.info("Collecting from %s (attempt %s)", source.name, attempt)
                all_records.extend(_fetch_rss(source, timeout=timeout, user_agent=user_agent))
                last_error = None
                break
            except Exception as err:
                last_error = err
                logger.warning("Source failed: %s, error=%s", source.name, err)
        if last_error is not None:
            logger.error("Give up source: %s", source.name)

    logger.info("Collected %s raw records", len(all_records))
    return all_records
