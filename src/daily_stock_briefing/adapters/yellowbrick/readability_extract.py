"""Extract readable article text from HTML using readability-lxml."""

from __future__ import annotations

import re

import httpx
from lxml import html as lxml_html
from readability.readability import Document

_DEFAULT_UA = (
    "Mozilla/5.0 (compatible; DailyStockBriefing/1.0; +https://example.com/bot)"
)


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
