from __future__ import annotations

from pathlib import Path

from daily_stock_briefing.domain.models import CompanyDisclosure, WatchlistItem
from press_release_collector.collectors.html_collector import collect_html
from press_release_collector.collectors.rss_collector import collect_rss
from press_release_collector.core.dedupe import dedupe_press_releases
from press_release_collector.core.normalize import normalize_press_release
from press_release_collector.core.storage import bulk_upsert_press_releases

EARNINGS_TERMS = (
    "announces results",
    "announces first quarter",
    "announces second quarter",
    "announces third quarter",
    "announces fourth quarter",
    "announces full year",
    "reports first quarter",
    "reports second quarter",
    "reports third quarter",
    "reports fourth quarter",
    "reports full year",
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


def _disclosure_kind(
    title: str,
    url: str,
    extra_earnings_terms: tuple[str, ...] = (),
) -> str:
    extra_earnings_terms = tuple(term.lower() for term in extra_earnings_terms)
    lowered = f"{title} {url}".lower()
    if any(term in lowered for term in IR_DECK_TERMS):
        return "ir_deck"
    if any(term in lowered for term in NON_EARNINGS_RESULTS_TERMS):
        return "press_release"
    if any(term in lowered for term in EARNINGS_TERMS + extra_earnings_terms):
        return "earnings"
    return "press_release"


def _is_rss_url(url: str) -> bool:
    lowered = url.lower()
    return (
        "/rss/" in lowered
        or "output=atom" in lowered
        or lowered.endswith(".rss")
        or lowered.endswith(".xml")
    )


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
        url = str(item.press_release_url)
        if _is_rss_url(url):
            if item.press_release_noise_terms:
                releases = collect_rss(
                    item.ticker,
                    item.name,
                    url,
                    extra_noise_terms=tuple(item.press_release_noise_terms),
                )[: self._max_items]
            else:
                releases = collect_rss(item.ticker, item.name, url)[: self._max_items]
        else:
            releases = collect_html(
                ticker=item.ticker,
                company_name=item.name,
                url=url,
                max_items=self._max_items,
                extra_skip_terms=tuple(item.press_release_skip_link_terms),
                override_link_terms=tuple(item.press_release_link_terms) or None,
                content_block_terms=frozenset(
                    term.lower() for term in item.press_release_content_block_terms
                ),
            )
        normalized = [normalize_press_release(release) for release in releases]
        unique = dedupe_press_releases(normalized)
        bulk_upsert_press_releases(self._db_path, unique)
        disclosures: list[CompanyDisclosure] = []
        for release in unique:
            kind = _disclosure_kind(
                release.title,
                release.url,
                extra_earnings_terms=tuple(item.disclosure_earnings_terms),
            )
            disclosures.append(
                CompanyDisclosure(
                    kind=kind,
                    title=release.title,
                    url=release.url,
                    summary=release.summary if kind != "ir_deck" else None,
                )
            )
        return disclosures
