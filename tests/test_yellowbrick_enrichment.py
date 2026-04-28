from unittest.mock import patch

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
    "daily_stock_briefing.services.yellowbrick_enrichment.fetch_latest_pitch_row",
    return_value=None,
)
def test_enrich_no_pitch_sets_message(mock_fetch: object) -> None:
    out = enrich_symbol_with_yellowbrick(_briefing(), None)
    assert out.yellowbrick_pitch is not None
    assert "레코드가 없습니다" in (out.yellowbrick_pitch.summary_ko or "")


@patch(
    "daily_stock_briefing.services.yellowbrick_enrichment.fetch_latest_pitch_row",
    return_value={
        "title": "Pitch",
        "summary_short": "Short English summary.",
        "summary_paragraph": None,
        "url": "https://example.com/article",
        "date_original": "2026-04-01",
        "given_ticker": "ZZTEST",
    },
)
@patch(
    "daily_stock_briefing.services.yellowbrick_enrichment.extract_readable_text",
    return_value="",
)
def test_enrich_uses_db_when_body_empty(mock_extract: object, mock_fetch: object) -> None:
    out = enrich_symbol_with_yellowbrick(_briefing(), None)
    assert out.yellowbrick_pitch is not None
    assert out.yellowbrick_pitch.article_url == "https://example.com/article"
    assert out.yellowbrick_pitch.summary_ko is not None
    assert "DB 요약" in out.yellowbrick_pitch.summary_ko
