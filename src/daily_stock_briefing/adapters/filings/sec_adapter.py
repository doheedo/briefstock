from datetime import datetime, timezone
from typing import Any

import httpx

from daily_stock_briefing.adapters.filings.base import (
    FilingProvider,
    build_filing_item,
    safe_normalize_filings,
)
from daily_stock_briefing.domain.models import FilingItem, WatchlistItem

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


def _parse_sec_filed_at(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _normalize_sec_cik(raw: dict[str, Any]) -> str | None:
    for key in ("cik", "cikNumber", "issuerCik"):
        value = raw.get(key)
        if value not in (None, ""):
            return str(int(str(value)))
    return None


def _build_sec_filing_url(accession: str, primary_document: str, cik: str | None) -> str:
    if cik:
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_document}"
    return f"https://www.sec.gov/Archives/edgar/data/{accession}/{primary_document}"


def _value_at(values: Any, index: int, default: str = "") -> str:
    if isinstance(values, list) and index < len(values):
        return str(values[index])
    return default


def _lookup_sec_cik(client: httpx.Client, ticker: str) -> str | None:
    response = client.get(SEC_COMPANY_TICKERS_URL)
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, dict):
        return None

    ticker_upper = ticker.strip().upper()
    for raw in payload.values():
        if not isinstance(raw, dict):
            continue
        if str(raw.get("ticker", "")).upper() != ticker_upper:
            continue
        try:
            return f"{int(str(raw['cik_str'])):010d}"
        except (KeyError, TypeError, ValueError):
            return None

    return None


def _recent_sec_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    filings = payload.get("filings", {})
    if not isinstance(filings, dict):
        return []

    recent = filings.get("recent", {})
    if not isinstance(recent, dict):
        return []

    accessions = recent.get("accessionNumber", [])
    if not isinstance(accessions, list):
        return []

    cik = payload.get("cik")
    rows: list[dict[str, Any]] = []
    for index, accession in enumerate(accessions):
        form = _value_at(recent.get("form", []), index)
        rows.append(
            {
                "accessionNumber": accession,
                "cik": cik,
                "form": form,
                "filingDate": _value_at(recent.get("filingDate", []), index),
                "primaryDocument": _value_at(
                    recent.get("primaryDocument", []), index, "index.htm"
                ),
                "primaryDocDescription": _value_at(
                    recent.get("primaryDocDescription", []), index, form
                ),
            }
        )
    return rows


def normalize_sec_filing(ticker: str, raw: dict[str, Any]) -> FilingItem:
    accession = str(raw["accessionNumber"]).replace("-", "")
    title = str(raw.get("primaryDocDescription") or raw.get("form") or "SEC filing")
    primary_document = str(raw.get("primaryDocument") or "index.htm")
    cik = _normalize_sec_cik(raw)

    return build_filing_item(
        id=accession,
        ticker=ticker,
        filing_type=str(raw["form"]),
        title=title,
        filed_at=_parse_sec_filed_at(str(raw["filingDate"])),
        filing_url=_build_sec_filing_url(accession, primary_document, cik),
        source_system="SEC",
        raw_excerpt=title,
    )


class SecFilingProvider(FilingProvider):
    def __init__(self, user_agent: str, timeout: float = 10.0) -> None:
        self._headers = {"User-Agent": user_agent}
        self._timeout = timeout

    def fetch_filings(self, item: WatchlistItem) -> list[FilingItem]:
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            cik = _lookup_sec_cik(client, item.ticker)
            if not cik:
                return []

            response = client.get(SEC_SUBMISSIONS_URL.format(cik=cik))
            response.raise_for_status()

        return safe_normalize_filings(
            _recent_sec_rows(response.json()),
            lambda raw: normalize_sec_filing(item.ticker, raw),
        )[:5]
