from __future__ import annotations

import logging
from types import SimpleNamespace

from press_release_collector.core.models import PressRelease

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised when optional dependency is installed
    import feedparser
except ImportError:  # pragma: no cover - local fallback path
    def _missing_feedparser_parse(url: str):
        raise RuntimeError("feedparser is not installed")

    feedparser = SimpleNamespace(parse=_missing_feedparser_parse)


def collect_rss(ticker: str, company_name: str, url: str) -> list[PressRelease]:
    try:
        feed = feedparser.parse(url)
    except Exception:
        logger.exception("RSS press release collection failed: %s", url)
        return []

    releases: list[PressRelease] = []
    for entry in getattr(feed, "entries", []) or []:
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""
        if not title or not link:
            continue
        published_at = (
            getattr(entry, "published", None)
            or getattr(entry, "updated", None)
            or None
        )
        summary = getattr(entry, "summary", None)
        content = getattr(entry, "content", None)
        if isinstance(content, list):
            content = " ".join(
                str(part.get("value", ""))
                for part in content
                if isinstance(part, dict)
            )
        releases.append(
            PressRelease.from_raw(
                ticker=ticker,
                company_name=company_name,
                title=title,
                url=link,
                published_at=published_at,
                source_name=url,
                source_type="official_rss",
                summary=summary,
                content=content or summary,
            )
        )
    return releases
