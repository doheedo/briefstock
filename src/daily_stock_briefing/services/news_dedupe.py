import re
from collections.abc import Iterable, Mapping
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

from daily_stock_briefing.domain.models import NewsItem


def _normalize_title(value: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else " "
        for character in value.strip()
    )
    return " ".join(normalized.split())


def _normalize_url(value: str) -> str:
    normalized = _normalize_url_or_none(value)
    if normalized is None:
        return value.strip().lower()
    return normalized


def _normalize_url_or_none(value: str) -> str | None:
    try:
        parts = urlsplit(value.strip())
        host = parts.hostname.lower() if parts.hostname else ""
        port = parts.port
    except ValueError:
        return None

    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    if port and not (
        (parts.scheme.lower() == "http" and port == 80)
        or (parts.scheme.lower() == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), host, path, "", ""))


def _normalized_story_url(item: NewsItem) -> str:
    canonical_url = _normalize_url_or_none(item.canonical_url)
    if canonical_url is not None:
        return canonical_url
    return _normalize_url(item.url)


def _is_duplicate(
    candidate: NewsItem,
    existing: NewsItem,
    *,
    window: timedelta,
) -> bool:
    if candidate.ticker != existing.ticker:
        return False

    candidate_url = _normalized_story_url(candidate)
    existing_url = _normalized_story_url(existing)
    if candidate_url and candidate_url == existing_url:
        return True

    candidate_title = _normalize_title(candidate.title)
    existing_title = _normalize_title(existing.title)
    if candidate_title != existing_title:
        return False

    return abs(candidate.published_at - existing.published_at) <= window


def _rank_item(item: NewsItem, source_ranks: Mapping[str, int]) -> tuple[int, object, str]:
    return (
        source_ranks.get(item.publisher, 0),
        item.published_at,
        item.id,
    )


def _build_groups(items: list[NewsItem], publish_window: timedelta) -> list[list[NewsItem]]:
    remaining = list(items)
    groups: list[list[NewsItem]] = []

    while remaining:
        seed = remaining.pop()
        group = [seed]
        changed = True
        while changed:
            changed = False
            next_remaining: list[NewsItem] = []
            for item in remaining:
                if any(_is_duplicate(item, existing, window=publish_window) for existing in group):
                    group.append(item)
                    changed = True
                else:
                    next_remaining.append(item)
            remaining = next_remaining
        groups.append(group)

    return groups


def dedupe_news(
    items: Iterable[NewsItem],
    *,
    source_ranks: Mapping[str, int] | None = None,
    publish_window: timedelta = timedelta(minutes=30),
) -> list[NewsItem]:
    ranks = source_ranks or {}
    groups = _build_groups(list(items), publish_window)
    selected = [max(group, key=lambda item: _rank_item(item, ranks)) for group in groups]

    return sorted(
        selected,
        key=lambda item: (item.published_at, item.id),
        reverse=True,
    )
