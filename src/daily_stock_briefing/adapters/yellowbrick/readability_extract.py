"""Extract Yellowbrick article links and readable article text using readability-lxml."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urljoin

import httpx
from lxml import html as lxml_html
from readability.readability import Document

_DEFAULT_UA = (
    "Mozilla/5.0 (compatible; DailyStockBriefing/1.0; +https://example.com/bot)"
)


@dataclass(frozen=True)
class YellowbrickArticleCandidate:
    read_more_url: str
    pitch_date: str | None = None


def _extract_date_iso(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)
    match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        dt = datetime.strptime(match.group(0), "%B %d, %Y")
    except ValueError:
        return None
    return dt.date().isoformat()


def find_recent_read_more_candidate(
    ticker_base: str,
    *,
    days: int = 30,
    timeout: float = 25.0,
) -> YellowbrickArticleCandidate | None:
    base = ticker_base.strip().upper()
    if not base:
        return None
    query = urlencode({"ticker": base})
    listing_url = f"https://www.joinyellowbrick.com/?{query}"
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": _DEFAULT_UA},
        ) as client:
            response = client.get(listing_url)
            response.raise_for_status()
            tree = lxml_html.fromstring(response.text)
    except Exception:
        return None

    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    anchors = tree.xpath("//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'read full article')]")
    for anchor in anchors:
        href = anchor.get("href")
        if not href:
            continue
        read_more_url = urljoin("https://www.joinyellowbrick.com", href)
        text_near = " ".join(anchor.xpath("./ancestor::*[position() <= 4]//text()"))
        date_iso = _extract_date_iso(text_near)
        if date_iso:
            try:
                if datetime.strptime(date_iso, "%Y-%m-%d").date() < cutoff:
                    continue
            except ValueError:
                pass
        return YellowbrickArticleCandidate(read_more_url=read_more_url, pitch_date=date_iso)
    return None


def extract_readable_text(url: str, *, timeout: float = 25.0, max_chars: int = 12000) -> str:
    """
    Fetch ``url`` and return plain text from readability's main content.
    Returns an empty string on failure.
    """
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": _DEFAULT_UA},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            raw = response.content
    except Exception:
        return ""

    try:
        doc = Document(raw)
        summary_html = doc.summary(html_partial=True)
        if not summary_html:
            return ""
        tree = lxml_html.fromstring(summary_html)
        text = tree.text_content()
    except Exception:
        return ""

    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text
