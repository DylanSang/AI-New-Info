from __future__ import annotations

from typing import Any


def build_timeline(event: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(event.get("timeline", []), key=lambda x: x["published_at"])


def timeline_text(event: dict[str, Any]) -> str:
    lines = [f'Event: {event["title"]}', "-" * 60]
    for point in build_timeline(event):
        lines.append(f'{point["published_at"]} | {point["source_name"]} | {point["article_url"]}')
    return "\n".join(lines)
