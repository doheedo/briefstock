from __future__ import annotations

import csv
from io import StringIO

import httpx

from daily_stock_briefing.domain.models import WagnHoldingItem

WAGN_SOURCE_URL = "https://www.wagonsetf.com/fund-summary"
WAGN_HOLDINGS_CSV_URL = (
    "https://wagonsetf.filepoint.live/assets/data/"
    "FilepointWagonsETF.40P8.P8_ETF_Holdings.csv"
)


def _parse_weight(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip().replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fetch_wagn_holdings_csv(url: str = WAGN_HOLDINGS_CSV_URL) -> tuple[str | None, list[WagnHoldingItem]]:
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
    text = response.text

    rows = csv.DictReader(StringIO(text))
    out: list[WagnHoldingItem] = []
    as_of: str | None = None
    for row in rows:
        weight = _parse_weight(row.get("Weightings"))
        if weight is None:
            continue
        ticker = (row.get("StockTicker") or "").strip() or "N/A"
        name = (row.get("SecurityName") or "").strip() or ticker
        if as_of is None:
            as_of = (row.get("Date") or "").strip() or None
        out.append(WagnHoldingItem(ticker=ticker, name=name, weight_pct=weight))
    out.sort(key=lambda item: item.weight_pct, reverse=True)
    return as_of, out
