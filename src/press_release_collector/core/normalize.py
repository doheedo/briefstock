from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dateutil import parser as date_parser

from press_release_collector.core.models import PressRelease

SOURCE_TYPES = {"official_rss", "official_html", "wire"}


def clean_spaces(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_title(title: str) -> str:
    return clean_spaces(title).lower()


def display_title(title: str) -> str:
    return clean_spaces(title)


def normalize_url(url: str) -> str:
    parts = urlsplit(clean_spaces(url))
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or parts.path,
            urlencode(query),
            "",
        )
    )


def normalize_datetime(value: str | None) -> str | None:
    if not value:
        return None
    dt = date_parser.parse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def normalize_source_type(value: str) -> str:
    lowered = clean_spaces(value).lower()
    if lowered not in SOURCE_TYPES:
        raise ValueError(f"unsupported source_type: {value}")
    return lowered


def make_uid(ticker: str, title: str, url: str) -> str:
    payload = "|".join([ticker.upper(), normalize_title(title), normalize_url(url)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_press_release(release: PressRelease) -> PressRelease:
    ticker = clean_spaces(release.ticker).upper()
    company_name = clean_spaces(release.company_name)
    title = display_title(release.title)
    url = normalize_url(release.url)
    source_type = normalize_source_type(release.source_type)
    uid = make_uid(ticker, title, url)
    return release.model_copy(
        update={
            "ticker": ticker,
            "company_name": company_name,
            "title": title,
            "url": url,
            "published_at": normalize_datetime(release.published_at),
            "source_name": clean_spaces(release.source_name),
            "source_type": source_type,
            "summary": clean_spaces(release.summary) or None,
            "content": clean_spaces(release.content) or None,
            "uid": uid,
            "collected_at": normalize_datetime(release.collected_at)
            or datetime.now(UTC).isoformat(),
        }
    )
