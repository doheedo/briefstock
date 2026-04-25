from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from daily_stock_briefing.domain.enums import (
    DailyPriority,
    EventCategory,
    SourcePriority,
    ThesisImpact,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class WatchlistItem(BaseModel):
    ticker: NonEmptyStr
    name: NonEmptyStr
    market: NonEmptyStr
    group: NonEmptyStr = "default"
    thesis: NonEmptyStr
    keywords: list[NonEmptyStr] = Field(min_length=1)
    aliases: list[NonEmptyStr] = Field(default_factory=list)
    exclude_keywords: list[NonEmptyStr] = Field(default_factory=list)
    thesis_questions: list[NonEmptyStr] = Field(default_factory=list)
    red_flags: list[NonEmptyStr] = Field(default_factory=list)
    positive_signals: list[NonEmptyStr] = Field(default_factory=list)
    min_keyword_matches: int = 1
    source_priority: list[SourcePriority] = Field(
        default_factory=lambda: [
            SourcePriority.FILINGS,
            SourcePriority.NEWS,
            SourcePriority.PRICE,
        ],
        min_length=1,
    )

    @field_validator("source_priority")
    @classmethod
    def validate_source_priority_unique(
        cls, value: list[SourcePriority]
    ) -> list[SourcePriority]:
        if len(value) != len(set(value)):
            raise ValueError("source_priority must not contain duplicates")
        return value


class PriceSnapshot(BaseModel):
    ticker: str
    previous_close: float
    close: float
    change: float
    change_pct: float
    currency: str
    as_of: datetime
    source: str
    return_5d_pct: float | None = None
    return_1m_pct: float | None = None
    return_1y_pct: float | None = None
    benchmark_ticker: str | None = "^GSPC"
    benchmark_return_1y_pct: float | None = None
    relative_return_1y_pct: float | None = None
    rsi_14: float | None = None
    chart_path: str | None = None


class NewsItem(BaseModel):
    id: str
    ticker: str
    title: str
    summary: str
    publisher: str
    url: str
    canonical_url: str
    published_at: datetime
    source: str
    matched_keywords: list[str] = Field(default_factory=list)


class FilingItem(BaseModel):
    id: str
    ticker: str
    filing_type: str
    title: str
    filed_at: datetime
    event_date: datetime | None = None
    filing_url: str
    source_system: str
    raw_excerpt: str = ""


class CompanyEvent(BaseModel):
    ticker: str
    category: EventCategory
    importance_score: int
    thesis_impact: ThesisImpact
    summary: str
    evidence: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class SymbolBriefing(BaseModel):
    watchlist_item: WatchlistItem
    price_snapshot: PriceSnapshot | None = None
    major_news: list[NewsItem] = Field(default_factory=list)
    filings: list[FilingItem] = Field(default_factory=list)
    derived_events: list[CompanyEvent] = Field(default_factory=list)
    thesis_summary: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    priority: DailyPriority = DailyPriority.LOW


class DailyBriefingReport(BaseModel):
    run_date: str
    market_summary: str
    symbol_briefings: list[SymbolBriefing]
    delivery_metadata: dict[str, str] = Field(default_factory=dict)
