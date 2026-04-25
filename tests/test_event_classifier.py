from datetime import datetime, timezone

from daily_stock_briefing.domain.enums import (
    DailyPriority,
    EventCategory,
    ThesisImpact,
)
from daily_stock_briefing.domain.models import (
    FilingItem,
    NewsItem,
    PriceSnapshot,
    WatchlistItem,
)
from daily_stock_briefing.services.report_builder import build_symbol_briefing


def _watchlist_item() -> WatchlistItem:
    return WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="US",
        thesis="credit quality and deposit funding",
        keywords=["LendingClub", "guidance"],
        source_priority=["filings", "news", "price"],
    )


def _news(title: str, summary: str = "") -> NewsItem:
    return NewsItem(
        id=title,
        ticker="LC",
        title=title,
        summary=summary,
        publisher="Reuters",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        published_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source="http_news",
        matched_keywords=["guidance"],
    )


def _price(change_pct: float) -> PriceSnapshot:
    return PriceSnapshot(
        ticker="LC",
        previous_close=10.0,
        close=10.0 * (1 + change_pct / 100),
        change=10.0 * (change_pct / 100),
        change_pct=change_pct,
        currency="USD",
        as_of=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source="yfinance",
    )


def test_negative_guidance_becomes_high_priority() -> None:
    briefing = build_symbol_briefing(
        _watchlist_item(),
        _price(-15.0),
        [_news("LendingClub cuts full-year guidance", "Guidance reduced.")],
        [],
    )

    assert briefing.derived_events[0].category == EventCategory.GUIDANCE
    assert briefing.derived_events[0].importance_score == 5
    assert briefing.derived_events[0].thesis_impact == ThesisImpact.NEGATIVE
    assert briefing.priority == DailyPriority.HIGH
    assert "negative" in briefing.thesis_summary
    assert briefing.follow_up_questions


def test_filing_offering_becomes_financing_event() -> None:
    filing = FilingItem(
        id="filing-1",
        ticker="LC",
        filing_type="8-K",
        title="Convertible notes offering",
        filed_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        filing_url="https://example.com/filing",
        source_system="SEC",
        raw_excerpt="Convertible notes offering",
    )

    briefing = build_symbol_briefing(_watchlist_item(), None, [], [filing])

    assert briefing.derived_events[0].category == EventCategory.FINANCING
    assert briefing.derived_events[0].importance_score == 4
    assert briefing.derived_events[0].source_refs == ["https://example.com/filing"]
    assert briefing.priority == DailyPriority.HIGH


def test_ownership_filings_do_not_raise_priority_without_related_news() -> None:
    filing = FilingItem(
        id="filing-2",
        ticker="LC",
        filing_type="4",
        title="FORM 4",
        filed_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        filing_url="https://example.com/form4",
        source_system="SEC",
        raw_excerpt="FORM 4",
    )

    briefing = build_symbol_briefing(_watchlist_item(), _price(0.5), [], [filing])

    assert briefing.derived_events[0].category == EventCategory.INSIDER_TRANSACTION
    assert briefing.derived_events[0].importance_score == 2
    assert briefing.derived_events[0].thesis_impact == ThesisImpact.NEUTRAL
    assert briefing.priority == DailyPriority.LOW
    assert briefing.thesis_summary == "No thesis-relevant update."
    assert briefing.follow_up_questions == []


def test_underperformance_question_names_actual_benchmark() -> None:
    price = _price(-1.0).model_copy(
        update={"benchmark_ticker": "^KS200", "relative_return_1y_pct": -25.0}
    )

    briefing = build_symbol_briefing(_watchlist_item(), price, [], [])

    assert briefing.follow_up_questions == [
        "Review long-term underperformance versus ^KS200."
    ]


def test_large_price_move_without_events_becomes_medium_priority() -> None:
    briefing = build_symbol_briefing(_watchlist_item(), _price(8.0), [], [])

    assert briefing.priority == DailyPriority.MEDIUM
    assert briefing.thesis_summary == "No thesis-relevant update."
    assert "Review price move" in briefing.follow_up_questions[0]


def test_noise_only_stays_low_priority() -> None:
    briefing = build_symbol_briefing(
        _watchlist_item(),
        _price(0.5),
        [_news("LendingClub mentioned in market roundup", "Roundup item.")],
        [],
    )

    assert briefing.derived_events[0].category == EventCategory.NOISE
    assert briefing.priority == DailyPriority.LOW
