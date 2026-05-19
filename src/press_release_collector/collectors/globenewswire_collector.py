from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from press_release_collector.collectors.html_collector import REQUEST_HEADERS
from press_release_collector.core.models import PressRelease
from press_release_collector.core.normalize import clean_spaces

logger = logging.getLogger(__name__)


def _date_only(value: str) -> str:
    parts = value.split()
    return " ".join(parts[:3]) if len(parts) >= 3 else value


def collect_globenewswire_search(
    ticker: str,
    company_name: str,
    url: str,
    *,
    timeout: float = 10.0,
    max_items: int = 6,
) -> list[PressRelease]:
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=REQUEST_HEADERS,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except Exception:
        logger.exception("GlobeNewswire search collection failed: %s", url)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    releases: list[PressRelease] = []
    for item in soup.select(".recentNewsH li.row"):
        link_node = item.select_one(".mainLink a[href]")
        if link_node is None:
            continue
        title = clean_spaces(link_node.get_text(" ", strip=True))
        link = urljoin(str(response.url), str(link_node.get("href") or ""))
        summary_node = item.select_one(".newsTxt")
        summary = (
            clean_spaces(summary_node.get_text(" ", strip=True))
            if summary_node is not None
            else None
        )
        date_node = item.select_one(".date-source")
        published_at = None
        if date_node is not None:
            date_text = clean_spaces(date_node.get_text(" ", strip=True)).split("|")[0].strip()
            published_at = _date_only(date_text)
        if not title or not link:
            continue
        releases.append(
            PressRelease.from_raw(
                ticker=ticker,
                company_name=company_name,
                title=title,
                url=link,
                published_at=published_at,
                source_name="www.globenewswire.com",
                source_type="official_html",
                summary=summary,
                content=summary,
            )
        )
        if len(releases) >= max_items:
            break
    return releases
