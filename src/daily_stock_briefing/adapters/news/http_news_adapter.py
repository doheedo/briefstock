from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from daily_stock_briefing.adapters.news.base import NewsProvider
from daily_stock_briefing.domain.models import NewsItem, WatchlistItem


def _canonicalize_url(url: str) -> str | None:
    try:
        parts = urlsplit(url)
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


def _match_keywords(item: WatchlistItem, raw: dict) -> list[str]:
    title = _coerce_text(raw.get("title"))
    description = _coerce_text(raw.get("description"))
    content = _coerce_text(raw.get("content"))
    if title is None or description is None or content is None:
        return []
    haystack = " ".join(
        [
            title,
            description,
            content,
        ]
    ).lower()
    terms = [*item.keywords, *item.aliases]
    return [keyword for keyword in terms if keyword.lower() in haystack]


def _contains_excluded_keyword(item: WatchlistItem, raw: dict) -> bool:
    title = _coerce_text(raw.get("title"))
    description = _coerce_text(raw.get("description"))
    content = _coerce_text(raw.get("content"))
    if title is None or description is None or content is None:
        return False
    haystack = " ".join([title, description, content]).lower()
    return any(keyword.lower() in haystack for keyword in item.exclude_keywords)


def _coerce_text(value: object, *, allow_none: bool = True) -> str | None:
    if value is None:
        return "" if allow_none else None
    if isinstance(value, str):
        return value
    return None


def _publisher_name(raw_source: object) -> str | None:
    if raw_source is None:
        return "unknown"
    if not isinstance(raw_source, dict):
        return None
    name = raw_source.get("name", "unknown")
    if not isinstance(name, str):
        return None
    return name


class HttpNewsProvider(NewsProvider):
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def fetch_news(self, item: WatchlistItem) -> list[NewsItem]:
        query_terms = [item.name, *item.aliases, *item.keywords]
        params = {"q": " OR ".join(query_terms), "apiKey": self._api_key}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(self._base_url, params=params)
                response.raise_for_status()
            payload = response.json()
        except Exception:
            return []
        if not isinstance(payload, dict):
            return []
        news: list[NewsItem] = []
        for raw in payload.get("articles", []):
            if not isinstance(raw, dict):
                continue
            if _contains_excluded_keyword(item, raw):
                continue
            matched_keywords = _match_keywords(item, raw)
            if len(matched_keywords) < item.min_keyword_matches:
                continue
            url = _coerce_text(raw.get("url"), allow_none=False)
            title = _coerce_text(raw.get("title"), allow_none=False)
            summary = _coerce_text(raw.get("description"))
            published_at = _coerce_text(raw.get("publishedAt"), allow_none=False)
            publisher = _publisher_name(raw.get("source"))
            if (
                not url
                or not title
                or not published_at
                or summary is None
                or publisher is None
            ):
                continue
            try:
                parsed_published_at = datetime.fromisoformat(
                    published_at.replace("Z", "+00:00")
                )
            except ValueError:
                continue
            if parsed_published_at.tzinfo is None:
                continue
            parsed_published_at = parsed_published_at.astimezone(UTC)
            canonical_url = _canonicalize_url(url)
            if canonical_url is None:
                continue

            news.append(
                NewsItem(
                    id=url,
                    ticker=item.ticker,
                    title=title,
                    summary=summary,
                    publisher=publisher,
                    url=url,
                    canonical_url=canonical_url,
                    published_at=parsed_published_at,
                    source="http_news",
                    matched_keywords=matched_keywords,
                )
            )
        return news
