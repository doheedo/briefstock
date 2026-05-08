from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from press_release_collector.core.models import PressRelease
from press_release_collector.core.normalize import clean_spaces

try:  # pragma: no cover - exercised when optional dependency is installed
    import trafilatura
except ImportError:  # pragma: no cover - local fallback path
    trafilatura = None

logger = logging.getLogger(__name__)

LINK_TERMS = (
    "news",
    "newsroom",
    "press",
    "release",
    "investor",
    "ir",
    "announcement",
    "results",
)
SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".zip")
DECK_TERMS = ("deck", "presentation", "investor")


def collect_html(
    *,
    ticker: str,
    company_name: str,
    url: str,
    timeout: float = 10.0,
    max_items: int = 8,
) -> list[PressRelease]:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            candidates = _candidate_links(response.text, url, max_items=max_items)
            releases: list[PressRelease] = []
            for link, fallback_title in candidates:
                if _is_link_only_deck(link, fallback_title):
                    releases.append(
                        PressRelease.from_raw(
                            ticker=ticker,
                            company_name=company_name,
                            title=fallback_title,
                            url=link,
                            source_name=urlsplit(link).netloc,
                            source_type="official_html",
                        )
                    )
                    continue
                try:
                    detail = client.get(link)
                    detail.raise_for_status()
                except Exception:
                    logger.warning("HTML press release detail fetch failed: %s", link)
                    continue
                releases.append(
                    _parse_detail(
                        ticker=ticker,
                        company_name=company_name,
                        url=link,
                        html=detail.text,
                        fallback_title=fallback_title,
                    )
                )
            return releases
    except Exception:
        logger.exception("HTML press release collection failed: %s", url)
        return []


def _candidate_links(
    html: str,
    base_url: str,
    *,
    max_items: int,
) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_host = urlsplit(base_url).netloc.lower()
    anchors = []
    for selector in ("article a[href]", "main a[href]", "h1 a[href]", "h2 a[href]", "h3 a[href]"):
        anchors.extend(soup.select(selector))
    anchors = anchors or soup.find_all("a", href=True)

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in anchors:
        title = clean_spaces(anchor.get_text(" ", strip=True))
        href = str(anchor.get("href") or "")
        link = urljoin(base_url, href)
        parts = urlsplit(link)
        lowered = f"{title} {parts.path}".lower()
        if parts.netloc.lower() != base_host:
            continue
        if parts.path.lower().endswith(SKIP_EXTENSIONS) and not _is_link_only_deck(
            link,
            title,
        ):
            continue
        if not any(term in lowered for term in LINK_TERMS):
            continue
        if link in seen or link.rstrip("/") == base_url.rstrip("/"):
            continue
        seen.add(link)
        out.append((link, title))
        if len(out) >= max_items:
            break
    return out


def _is_link_only_deck(url: str, title: str) -> bool:
    lowered = f"{title} {url}".lower()
    return urlsplit(url).path.lower().endswith(".pdf") and any(
        term in lowered for term in DECK_TERMS
    )


def _parse_detail(
    *,
    ticker: str,
    company_name: str,
    url: str,
    html: str,
    fallback_title: str,
) -> PressRelease:
    soup = BeautifulSoup(html, "html.parser")
    title = _title(soup) or fallback_title
    published_at = _published_at(soup)
    extracted = (
        trafilatura.extract(html, include_comments=False, include_tables=False)
        if trafilatura is not None
        else None
    )
    content = clean_spaces(extracted) if extracted else _paragraph_text(soup)
    summary = _summary(content)
    return PressRelease.from_raw(
        ticker=ticker,
        company_name=company_name,
        title=title,
        url=url,
        published_at=published_at,
        source_name=urlsplit(url).netloc,
        source_type="official_html",
        summary=summary,
        content=content,
    )


def _title(soup: BeautifulSoup) -> str | None:
    for selector in ("h1", "h2", "title"):
        node = soup.select_one(selector)
        if node:
            text = clean_spaces(node.get_text(" ", strip=True))
            if text:
                return text
    return None


def _published_at(soup: BeautifulSoup) -> str | None:
    time_node = soup.find("time")
    if time_node:
        value = time_node.get("datetime") or time_node.get_text(" ", strip=True)
        if value:
            return str(value)
    text = soup.get_text(" ", strip=True)
    match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
    return match.group(0) if match else None


def _paragraph_text(soup: BeautifulSoup) -> str | None:
    paragraphs = [
        clean_spaces(p.get_text(" ", strip=True))
        for p in soup.find_all("p")
        if _is_content_candidate(clean_spaces(p.get_text(" ", strip=True)))
    ]
    return clean_spaces(" ".join(paragraphs)) or None


def _is_content_candidate(text: str) -> bool:
    lowered = text.lower()
    if len(text) < 35:
        return False
    if "copyright" in lowered or "all rights reserved" in lowered:
        return False
    if lowered in {"address", "constellation software inc."}:
        return False
    return True


def _summary(content: str | None) -> str | None:
    if not content:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", content)
    return clean_spaces(" ".join(sentences[:2]))[:500] or None
