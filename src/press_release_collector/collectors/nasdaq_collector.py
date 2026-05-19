from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx

from press_release_collector.collectors.html_collector import (
    REQUEST_HEADERS,
    _parse_detail,
)
from press_release_collector.core.models import PressRelease

logger = logging.getLogger(__name__)

NASDAQ_BASE_URL = "https://www.nasdaq.com"
NASDAQ_HEADERS = {
    **REQUEST_HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{NASDAQ_BASE_URL}/",
}


def _clean_nasdaq_text(value: str) -> str:
    return value.replace("ĸį", "®").replace("ĸâ", "™")


def collect_nasdaq_press_releases(
    ticker: str,
    company_name: str,
    *,
    timeout: float = 10.0,
    max_items: int = 6,
) -> list[PressRelease]:
    symbol = ticker.split(".")[0].upper()
    api_url = (
        f"{NASDAQ_BASE_URL}/api/news/topic/press_release"
        f"?q=symbol:{symbol}|assetclass:STOCKS&limit={max_items}&offset=0"
    )
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=NASDAQ_HEADERS,
        ) as client:
            response = client.get(api_url)
            response.raise_for_status()
            rows = response.json().get("data", {}).get("rows", [])
            releases: list[PressRelease] = []
            for row in rows[:max_items]:
                if not isinstance(row, dict):
                    continue
                title = _clean_nasdaq_text(str(row.get("title") or "").strip())
                path = str(row.get("url") or "").strip()
                if not title or not path:
                    continue
                detail_url = urljoin(NASDAQ_BASE_URL, path)
                try:
                    detail = client.get(detail_url)
                    detail.raise_for_status()
                except Exception:
                    logger.warning("NASDAQ press release detail fetch failed: %s", detail_url)
                    releases.append(
                        PressRelease.from_raw(
                            ticker=ticker,
                            company_name=company_name,
                            title=title,
                            url=detail_url,
                            published_at=str(row.get("created") or "") or None,
                            source_name="www.nasdaq.com",
                            source_type="official_html",
                        )
                    )
                    continue
                release = _parse_detail(
                    ticker=ticker,
                    company_name=company_name,
                    url=detail_url,
                    html=detail.text,
                    fallback_title=title,
                )
                releases.append(
                    release.model_copy(
                        update={
                            "title": _clean_nasdaq_text(release.title),
                            "published_at": str(row.get("created") or "")
                            or release.published_at,
                            "source_type": "official_html",
                        }
                    )
                )
            return releases
    except Exception:
        logger.exception("NASDAQ press release collection failed: %s", api_url)
        return []
