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
from daily_stock_briefing.services.research_links import build_research_links

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
    item: WatchlistItem,
    price_snapshot: PriceSnapshot | None,
    events: list,
    filing_items: list[FilingItem],
) -> list[str]:
    questions: list[str] = []
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
        corr = price_snapshot.benchmark_corr_20d
        if corr is not None:
            questions.append(
                f"Review long-term underperformance versus {benchmark} with 20D correlation ({corr:.2f})."
            )
        else:
            questions.append(f"Review long-term underperformance versus {benchmark}.")

    has_8k = any((f.filing_type or "").strip().upper() == "8-K" for f in filing_items)
    has_insider = any(
        (f.filing_type or "").strip().upper() in {"3", "4", "5", "144"}
        for f in filing_items
    )
    if has_8k:
        if item.ticker.upper() in {"BRK-B", "BRK.B", "BRK"}:
            questions.append(
                "Summarize latest 8-K items and assess impact on insurance float trajectory."
            )
        else:
            questions.append(
                "Summarize latest 8-K items and assess direct thesis impact."
            )
    if has_insider:
        questions.append(
            "Calculate insider net buy amount versus annual compensation (%); flag if 50% or higher."
        )
    if item.ticker.upper() == "UPST":
        questions.append(
            "Identify next release timing for model-performance data and key competitor updates."
        )
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
        follow_up_questions=_build_follow_up_questions(
            item,
            price_snapshot,
            events,
            filing_items,
        ),
        priority=priority,
        research_links=build_research_links(item),
    )
