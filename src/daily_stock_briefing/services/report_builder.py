from daily_stock_briefing.domain.enums import DailyPriority, ThesisImpact
from daily_stock_briefing.domain.models import (
    FilingItem,
    NewsItem,
    PriceSnapshot,
    SymbolBriefing,
    WatchlistItem,
)
from daily_stock_briefing.services.event_classifier import (
    classify_filing_event,
    classify_news_event,
)

PRICE_MOVE_MEDIUM_THRESHOLD = 5.0


def _priority_for_events(
    events: list,
    price_snapshot: PriceSnapshot | None,
) -> DailyPriority:
    if any(event.thesis_impact == ThesisImpact.NEGATIVE for event in events):
        return DailyPriority.HIGH
    if any(event.importance_score >= 4 for event in events):
        return DailyPriority.HIGH
    if any(event.importance_score == 3 for event in events):
        return DailyPriority.MEDIUM
    if price_snapshot and abs(price_snapshot.change_pct) >= PRICE_MOVE_MEDIUM_THRESHOLD:
        return DailyPriority.MEDIUM
    return DailyPriority.LOW


def _build_follow_up_questions(
    price_snapshot: PriceSnapshot | None,
    events: list,
) -> list[str]:
    questions: list[str] = []
    if any(
        event.importance_score >= 3
        or event.thesis_impact
        in {ThesisImpact.POSITIVE, ThesisImpact.NEGATIVE, ThesisImpact.UNKNOWN}
        for event in events
    ):
        questions.append("Does this change the core thesis today?")
    if price_snapshot and abs(price_snapshot.change_pct) >= PRICE_MOVE_MEDIUM_THRESHOLD:
        questions.append(
            f"Review price move of {price_snapshot.change_pct:.1f}% against news and filings."
        )
    if price_snapshot and price_snapshot.rsi_14 is not None:
        if price_snapshot.rsi_14 < 30:
            questions.append(
                "RSI is below 30; check whether the move is event-driven or broad market weakness."
            )
        elif price_snapshot.rsi_14 > 70:
            questions.append(
                "RSI is above 70; check whether the move reflects fundamentals or short-term overextension."
            )
    if (
        price_snapshot
        and price_snapshot.relative_return_1y_pct is not None
        and price_snapshot.relative_return_1y_pct <= -20
    ):
        benchmark = price_snapshot.benchmark_ticker or "^GSPC"
        questions.append(f"Review long-term underperformance versus {benchmark}.")
    return questions


def build_symbol_briefing(
    item: WatchlistItem,
    price_snapshot: PriceSnapshot | None,
    news_items: list[NewsItem],
    filing_items: list[FilingItem],
) -> SymbolBriefing:
    events = [classify_news_event(item, news) for news in news_items[:3]]
    events.extend(classify_filing_event(item, filing) for filing in filing_items[:3])
    priority = _priority_for_events(events, price_snapshot)

    thesis_summary = "No thesis-relevant update."
    thesis_events = [
        event
        for event in events
        if event.thesis_impact
        in {ThesisImpact.POSITIVE, ThesisImpact.NEGATIVE, ThesisImpact.UNKNOWN}
    ]
    if thesis_events:
        first = thesis_events[0]
        thesis_summary = f"{first.thesis_impact.value}: {first.summary}"

    return SymbolBriefing(
        watchlist_item=item,
        price_snapshot=price_snapshot,
        major_news=news_items[:3],
        filings=filing_items[:3],
        derived_events=events,
        thesis_summary=thesis_summary,
        follow_up_questions=_build_follow_up_questions(price_snapshot, events),
        priority=priority,
    )
