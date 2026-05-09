from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from press_release_collector.core.models import PressRelease
from press_release_collector.core.normalize import clean_spaces

try:  # pragma: no cover - exercised when optional dependency is installed
    import trafilatura
except ImportError:  # pragma: no cover - local fallback path
    trafilatura = None

logger = logging.getLogger(__name__)

REQUEST_HEADERS = {
    "User-Agent": "briefstock-press-release-collector/0.1 (+https://github.com/doheedo/briefstock)",
}

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
SKIP_EXTENSIONS = (".jpg", ".jpeg", ".png", ".zip")
LINK_ONLY_PDF_TERMS = (
    "deck",
    "presentation",
    "investor",
    "press",
    "release",
    "results",
    "earnings",
)
GENERIC_DETAIL_TITLES = {
    "news",
    "press releases",
    "press release",
    "release details",
    "press release details",
    "investor relations",
}
SKIP_LINK_TERMS = (
    "email-alerts",
    "in-the-news",
    "board-of-directors",
    "investor-charter",
    "/about-us/investor-relations",
    "/about-us/investor",
    "/about-us/qfr",
    "/about-us/voting-result",
    "au-ir-archive",
    "annual-reports",
    "archived-annual-documents",
    "esg-report",
    "investor-faqs",
    "investors-faqs",
    "lombard",
    "prudential",
    "pruamc",
    "contacts",
    "news-room",
)


def collect_html(
    *,
    ticker: str,
    company_name: str,
    url: str,
    timeout: float = 10.0,
    max_items: int = 8,
) -> list[PressRelease]:
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=REQUEST_HEADERS,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            candidates = _candidate_links(
                response.text,
                str(response.url),
                max_items=max_items,
            )
            releases: list[PressRelease] = []
            for link, fallback_title in candidates:
                if _is_link_only_pdf(link, fallback_title):
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
    out = _filter_candidate_anchors(anchors, base_url, base_host, max_items=max_items)
    if out:
        return out
    return _filter_candidate_anchors(
        soup.find_all("a", href=True),
        base_url,
        base_host,
        max_items=max_items,
    )


def _filter_candidate_anchors(
    anchors,
    base_url: str,
    base_host: str,
    *,
    max_items: int,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in anchors:
        title = clean_spaces(anchor.get_text(" ", strip=True))
        href = str(anchor.get("href") or "")
        link = urljoin(base_url, href)
        title = title or _title_from_url(link)
        parts = urlsplit(link)
        lowered = f"{title} {parts.path}".lower()
        if parts.netloc.lower() != base_host:
            continue
        if _should_skip_link(link, title):
            continue
        if parts.path.lower().endswith(SKIP_EXTENSIONS):
            continue
        if not _has_link_term(lowered):
            continue
        if link in seen or _same_document(link, base_url):
            continue
        seen.add(link)
        out.append((link, title))
        if len(out) >= max_items:
            break
    return out


def _has_link_term(text: str) -> bool:
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text)
        for term in LINK_TERMS
    )


def _title_from_url(url: str) -> str:
    stem = unquote(PurePosixPath(urlsplit(url).path).stem)
    title = re.sub(r"[-_]+", " ", stem)
    return clean_spaces(title).title()


def _should_skip_link(url: str, title: str = "") -> bool:
    lowered = f"{title} {url}".lower()
    path = urlsplit(url).path.rstrip("/").lower()
    return (
        any(term in lowered for term in SKIP_LINK_TERMS)
        or path == "/news-and-stories"
        or path == "/investors/financial-results-and-reports"
    )


def _same_document(link: str, base_url: str) -> bool:
    link_parts = urlsplit(link)
    base_parts = urlsplit(base_url)
    return (
        link_parts.scheme.lower(),
        link_parts.netloc.lower(),
        link_parts.path.rstrip("/"),
        link_parts.query,
    ) == (
        base_parts.scheme.lower(),
        base_parts.netloc.lower(),
        base_parts.path.rstrip("/"),
        base_parts.query,
    )


def _is_link_only_pdf(url: str, title: str) -> bool:
    lowered = f"{title} {url}".lower()
    return urlsplit(url).path.lower().endswith(".pdf") and any(
        term in lowered for term in LINK_ONLY_PDF_TERMS
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
    published_at = _published_at(soup) or _published_at_from_url(url)
    extracted = (
        trafilatura.extract(html, include_comments=False, include_tables=False)
        if trafilatura is not None
        else None
    )
    extracted_content = clean_spaces(extracted) if extracted else None
    paragraph_content = _paragraph_text(soup)
    content = (
        paragraph_content
        if _looks_like_navigation(extracted_content) and paragraph_content
        else extracted_content or paragraph_content
    )
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
            if text and text.lower() not in GENERIC_DETAIL_TITLES:
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


def _published_at_from_url(url: str) -> str | None:
    path = urlsplit(url).path
    slash_match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})(?:/|$)", path)
    if slash_match:
        year, month, day = slash_match.groups()
        return f"{year}-{month}-{day}"
    dash_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", path)
    return dash_match.group(1) if dash_match else None


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


def _looks_like_navigation(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    nav_terms = (
        "about us",
        "management team",
        "contact us",
        "investor relations",
        "board of directors",
        "corporate documents",
        "shareholder",
    )
    return sum(1 for term in nav_terms if term in lowered) >= 4


def _summary(content: str | None) -> str | None:
    if not content:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", content)
    return clean_spaces(" ".join(sentences[:2]))[:500] or None
