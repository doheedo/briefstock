import io
import zipfile
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree

import httpx

from daily_stock_briefing.adapters.filings.base import (
    FilingProvider,
    build_filing_item,
    safe_normalize_filings,
)
from daily_stock_briefing.domain.models import FilingItem, WatchlistItem

DART_CORP_CODES_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_FILINGS_URL = "https://opendart.fss.or.kr/api/list.json"


def _parse_dart_filed_at(value: str) -> datetime:
    return datetime.fromisoformat(f"{value}T00:00:00+09:00").astimezone(timezone.utc)


def _load_dart_corp_codes(client: httpx.Client, api_key: str) -> dict[str, str]:
    response = client.get(DART_CORP_CODES_URL, params={"crtfc_key": api_key})
    response.raise_for_status()

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            xml_names = [
                name for name in archive.namelist() if name.lower().endswith(".xml")
            ]
            if not xml_names:
                return {}
            xml_payload = archive.read(xml_names[0])
    except (OSError, KeyError, zipfile.BadZipFile):
        return {}

    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return {}

    corp_codes: dict[str, str] = {}
    for node in root.findall(".//list"):
        stock_code = (node.findtext("stock_code") or "").strip().upper()
        corp_code = (node.findtext("corp_code") or "").strip()
        if stock_code and corp_code:
            corp_codes[stock_code] = corp_code
    return corp_codes


def _lookup_dart_corp_code(
    client: httpx.Client, api_key: str, ticker: str
) -> str | None:
    ticker_upper = ticker.strip().upper().split(".", 1)[0]
    return _load_dart_corp_codes(client, api_key).get(ticker_upper)


def normalize_dart_filing(ticker: str, raw: dict[str, Any]) -> FilingItem:
    title = str(raw.get("report_nm") or "DART filing")
    receipt_number = str(raw["rcept_no"])

    return build_filing_item(
        id=receipt_number,
        ticker=ticker,
        filing_type=title,
        title=title,
        filed_at=_parse_dart_filed_at(str(raw["rcept_dt"])),
        filing_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_number}",
        source_system="DART",
        raw_excerpt=str(raw.get("rm") or raw.get("flr_nm") or ""),
    )


class DartFilingProvider(FilingProvider):
    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._corp_codes_by_stock: dict[str, str] | None = None

    def fetch_filings(self, item: WatchlistItem) -> list[FilingItem]:
        with httpx.Client(timeout=self._timeout) as client:
            corp_code = self._lookup_corp_code(client, item.ticker)
            if not corp_code:
                return []

            response = client.get(
                DART_FILINGS_URL,
                params={
                    "crtfc_key": self._api_key,
                    "corp_code": corp_code,
                    "page_count": 5,
                },
            )
            response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            return []

        raw_filings = payload.get("list", [])
        if not isinstance(raw_filings, list):
            return []

        return safe_normalize_filings(
            raw_filings,
            lambda raw: normalize_dart_filing(item.ticker, raw),
        )

    def _lookup_corp_code(self, client: httpx.Client, ticker: str) -> str | None:
        if self._corp_codes_by_stock is None:
            self._corp_codes_by_stock = _load_dart_corp_codes(client, self._api_key)
        ticker_upper = ticker.strip().upper().split(".", 1)[0]
        return self._corp_codes_by_stock.get(ticker_upper)
