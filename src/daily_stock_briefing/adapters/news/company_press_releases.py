from __future__ import annotations

from pathlib import Path

from daily_stock_briefing.domain.models import CompanyDisclosure, WatchlistItem
from press_release_collector.collectors.html_collector import collect_html
from press_release_collector.core.dedupe import dedupe_press_releases
from press_release_collector.core.normalize import normalize_press_release
from press_release_collector.core.storage import bulk_upsert_press_releases

EARNINGS_TERMS = (
    "announces results",
    "financial results",
    "earnings",
    "quarter ended",
    "year ended",
    "실적",
)
NON_EARNINGS_RESULTS_TERMS = ("results of voting", "voting for directors")
IR_DECK_TERMS = (
    "earnings presentation",
    "analyst presentation",
    "investor presentation",
    "presentation deck",
    "presentation.pdf",
    "ir deck",
    "investor deck",
    "webcast",
)


def _disclosure_kind(title: str, url: str) -> str:
    lowered = f"{title} {url}".lower()
    if any(term in lowered for term in IR_DECK_TERMS):
        return "ir_deck"
    if any(term in lowered for term in NON_EARNINGS_RESULTS_TERMS):
        return "press_release"
    if any(term in lowered for term in EARNINGS_TERMS):
        return "earnings"
    return "press_release"


class CompanyPressReleaseProvider:
    def __init__(
        self,
        *,
        db_path: Path = Path("data/press_releases.sqlite"),
        max_items: int = 6,
    ) -> None:
        self._db_path = db_path
        self._max_items = max_items

    def fetch_disclosures(self, item: WatchlistItem) -> list[CompanyDisclosure]:
        if not item.press_release_url:
            return []
        releases = collect_html(
            ticker=item.ticker,
            company_name=item.name,
            url=str(item.press_release_url),
            max_items=self._max_items,
        )
        normalized = [normalize_press_release(release) for release in releases]
        unique = dedupe_press_releases(normalized)
        bulk_upsert_press_releases(self._db_path, unique)
        disclosures: list[CompanyDisclosure] = []
        for release in unique:
            kind = _disclosure_kind(release.title, release.url)
            disclosures.append(
                CompanyDisclosure(
                    kind=kind,
                    title=release.title,
                    url=release.url,
                    summary=release.summary if kind != "ir_deck" else None,
                )
            )
        return disclosures
