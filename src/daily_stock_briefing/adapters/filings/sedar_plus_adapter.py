from datetime import datetime, timezone
from hashlib import sha256

import httpx

from daily_stock_briefing.adapters.filings.base import FilingProvider, build_filing_item
from daily_stock_briefing.domain.models import FilingItem, WatchlistItem

SEDAR_REPORTING_ISSUERS_URL = (
    "https://sedarplus.ca/csa-party/service/create.html"
    "?_locale=fr&service=searchReportingIssuers&targetAppCode=csa-party"
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class SedarPlusFilingProvider(FilingProvider):
    """
    Best-effort SEDAR+ provider for Canadian issuers.

    SEDAR+ applies anti-bot protections, so this provider intentionally degrades
    gracefully to an empty list if content cannot be fetched or parsed.
    """

    def __init__(self, timeout: float = 12.0) -> None:
        self._timeout = timeout

    def fetch_filings(self, item: WatchlistItem) -> list[FilingItem]:
        query = item.name.strip()
        if not query:
            return []
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                response = client.get(
                    SEDAR_REPORTING_ISSUERS_URL,
                    params={"search": query},
                )
                response.raise_for_status()
        except Exception:
            return []

        body = response.text
        if not body:
            return []
        lowered = body.lower()
        # Anti-bot or generic error page; treat as unavailable and move on.
        if "ssjsconnectorobj" in lowered or "unexpected system error" in lowered:
            return []

        item_name = item.name.strip().lower()
        if item_name and item_name not in lowered:
            return []

        filing_id = sha256(f"sedar:{item.ticker}:{item.name}".encode("utf-8")).hexdigest()[:16]
        return [
            build_filing_item(
                id=f"sedar-{filing_id}",
                ticker=item.ticker,
                filing_type="SEDAR+ profile",
                title=f"SEDAR+ reporting issuer lookup for {item.name}",
                filed_at=_now_utc(),
                filing_url=SEDAR_REPORTING_ISSUERS_URL,
                source_system="SEDAR+",
                raw_excerpt=f"Query: {item.name}",
            )
        ]
