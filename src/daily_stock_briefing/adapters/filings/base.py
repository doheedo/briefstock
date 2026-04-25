from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from daily_stock_briefing.domain.models import FilingItem, WatchlistItem


class FilingProvider(ABC):
    @abstractmethod
    def fetch_filings(self, item: WatchlistItem) -> list[FilingItem]:
        raise NotImplementedError


def build_filing_item(
    *,
    id: str,
    ticker: str,
    filing_type: str,
    title: str,
    filed_at: datetime,
    filing_url: str,
    source_system: str,
    raw_excerpt: str = "",
    event_date: datetime | None = None,
) -> FilingItem:
    return FilingItem(
        id=id,
        ticker=ticker,
        filing_type=filing_type,
        title=title,
        filed_at=filed_at,
        event_date=event_date,
        filing_url=filing_url,
        source_system=source_system,
        raw_excerpt=raw_excerpt,
    )


def safe_normalize_filings(
    raw_items: Iterable[Any],
    normalizer: Callable[[dict[str, Any]], FilingItem],
) -> list[FilingItem]:
    filings: list[FilingItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            filings.append(normalizer(raw))
        except (KeyError, TypeError, ValueError):
            continue
    return filings
