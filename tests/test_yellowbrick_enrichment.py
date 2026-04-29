from unittest.mock import patch

from daily_stock_briefing.adapters.yellowbrick.readability_extract import (
    YellowbrickArticleCandidate,
)
from daily_stock_briefing.domain.enums import DailyPriority
from daily_stock_briefing.domain.models import SymbolBriefing, WatchlistItem
from daily_stock_briefing.services.yellowbrick_enrichment import enrich_symbol_with_yellowbrick


def _item() -> WatchlistItem:
    return WatchlistItem(
        ticker="ZZTEST",
        name="Test",
        market="US",
        thesis="t",
        keywords=["k"],
    )


def _briefing() -> SymbolBriefing:
    return SymbolBriefing(
        watchlist_item=_item(),
        thesis_summary="ok",
        priority=DailyPriority.LOW,
    )


@patch(
    "daily_stock_briefing.services.yellowbrick_enrichment.find_recent_read_more_candidate",
    return_value=None,
)
def test_enrich_no_pitch_sets_message(mock_fetch: object) -> None:
    out = enrich_symbol_with_yellowbrick(_briefing(), None)
    assert out.yellowbrick_pitch is not None
    assert "Read full article 항목이 없습니다" in (out.yellowbrick_pitch.summary_ko or "")


@patch(
    "daily_stock_briefing.services.yellowbrick_enrichment.find_recent_read_more_candidate",
    return_value=YellowbrickArticleCandidate(
        read_more_url="https://example.com/read-more",
        pitch_date="2026-04-01",
    ),
)
@patch(
    "daily_stock_briefing.services.yellowbrick_enrichment.extract_readable_text",
    return_value="This is extracted article body from read more link.",
)
def test_enrich_uses_read_more_body(mock_extract: object, mock_fetch: object) -> None:
    out = enrich_symbol_with_yellowbrick(_briefing(), None)
    assert out.yellowbrick_pitch is not None
    assert out.yellowbrick_pitch.article_url == "https://example.com/read-more"
    assert out.yellowbrick_pitch.pitch_date == "2026-04-01"
    assert out.yellowbrick_pitch.summary_ko is not None
    assert "extracted article body" in out.yellowbrick_pitch.summary_ko
