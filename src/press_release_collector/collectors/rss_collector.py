from __future__ import annotations

import logging
import re
from types import SimpleNamespace
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from press_release_collector.core.models import PressRelease
from press_release_collector.core.normalize import clean_spaces

logger = logging.getLogger(__name__)

GOOGLE_NEWS_NOISE_TERMS = (
    "seeking alpha",
    "investopedia",
    "earnings preview",
    "price target",
    "stock to move",
    "takes questions",
    "class action",
    "investor alert",
    "shareholder investigation",
    "lead plaintiff",
    "law firm",
)
MAX_SUMMARY_LENGTH = 500

try:  # pragma: no cover - exercised when optional dependency is installed
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:  # pragma: no cover - local fallback path
    def _missing_feedparser_parse(url: str):
        raise RuntimeError("feedparser is not installed")

    feedparser = SimpleNamespace(parse=_missing_feedparser_parse)
    FEEDPARSER_AVAILABLE = False


def collect_rss(
    ticker: str,
    company_name: str,
    url: str,
    extra_noise_terms: tuple[str, ...] = (),
) -> list[PressRelease]:
    if not FEEDPARSER_AVAILABLE:
        return _collect_rss_xml(ticker, company_name, url, extra_noise_terms)
    try:
        feed = feedparser.parse(url)
    except Exception:
        logger.warning("feedparser RSS collection failed, trying XML fallback: %s", url)
        return _collect_rss_xml(ticker, company_name, url, extra_noise_terms)

    releases: list[PressRelease] = []
    for entry in getattr(feed, "entries", []) or []:
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""
        if not title or not link:
            continue
        if _is_google_news_noise(url, title, extra_noise_terms):
            continue
        published_at = (
            getattr(entry, "published", None)
            or getattr(entry, "updated", None)
            or None
        )
        summary = _clean_feed_text(getattr(entry, "summary", None))
        content = getattr(entry, "content", None)
        if isinstance(content, list):
            content = " ".join(
                str(part.get("value", ""))
                for part in content
                if isinstance(part, dict)
            )
        content = summary
        releases.append(
            PressRelease.from_raw(
                ticker=ticker,
                company_name=company_name,
                title=title,
                url=urljoin(url, link),
                published_at=published_at,
                source_name=url,
                source_type="official_rss",
                summary=summary,
                content=content,
            )
        )
    return releases


def _collect_rss_xml(
    ticker: str,
    company_name: str,
    url: str,
    extra_noise_terms: tuple[str, ...] = (),
) -> list[PressRelease]:
    try:
        response = httpx.get(
            url,
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "briefstock-press-release-collector/0.1"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception:
        logger.exception("RSS XML fallback collection failed: %s", url)
        return []

    releases: list[PressRelease] = []
    for item in root.findall(".//item"):
        title = _xml_text(item, "title")
        link = _xml_text(item, "link")
        if not title or not link:
            continue
        if _is_google_news_noise(url, title, extra_noise_terms):
            continue
        summary = _clean_feed_text(_xml_text(item, "description"))
        releases.append(
            PressRelease.from_raw(
                ticker=ticker,
                company_name=company_name,
                title=title,
                url=urljoin(url, link),
                published_at=_xml_text(item, "pubDate"),
                source_name=url,
                source_type="official_rss",
                summary=summary,
                content=summary,
            )
        )
    if releases:
        return releases

    atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", atom_ns):
        title = _xml_text(entry, "atom:title", atom_ns)
        link_node = entry.find("atom:link", atom_ns)
        link = link_node.get("href", "") if link_node is not None else ""
        if not title or not link:
            continue
        if _is_google_news_noise(url, title, extra_noise_terms):
            continue
        summary = _xml_text(entry, "atom:summary", atom_ns) or _xml_text(
            entry, "atom:content", atom_ns
        )
        summary = _clean_feed_text(summary)
        releases.append(
            PressRelease.from_raw(
                ticker=ticker,
                company_name=company_name,
                title=title,
                url=link,
                published_at=_xml_text(entry, "atom:published", atom_ns)
                or _xml_text(entry, "atom:updated", atom_ns),
                source_name=url,
                source_type="official_rss",
                summary=summary,
                content=summary,
            )
        )
    return releases


def _clean_feed_text(value: str | None) -> str | None:
    text = clean_spaces(value)
    if not text:
        return None
    if "<" in text and ">" in text:
        text = clean_spaces(BeautifulSoup(text, "html.parser").get_text(" "))
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text[:MAX_SUMMARY_LENGTH] or None


def _xml_text(node: ET.Element, path: str, ns: dict[str, str] | None = None) -> str | None:
    child = node.find(path, ns or {})
    if child is None or child.text is None:
        return None
    return child.text.strip() or None


def _is_google_news_noise(
    source_url: str,
    title: str,
    extra_noise_terms: tuple[str, ...] = (),
) -> bool:
    if "news.google.com/rss/search" not in source_url.lower():
        return False
    extra_noise_terms = tuple(term.lower() for term in extra_noise_terms)
    lowered = title.lower()
    return any(term in lowered for term in GOOGLE_NEWS_NOISE_TERMS + extra_noise_terms)
