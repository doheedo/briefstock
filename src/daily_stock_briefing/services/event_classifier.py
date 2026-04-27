from daily_stock_briefing.domain.enums import EventCategory, ThesisImpact
from daily_stock_briefing.domain.models import (
    CompanyEvent,
    FilingItem,
    NewsItem,
    WatchlistItem,
)

NEGATIVE_TERMS = ("cut", "lower", "miss", "weak", "delay", "lawsuit", "probe")
POSITIVE_TERMS = ("raise", "beat", "strong", "win", "approval", "expands")
OWNERSHIP_FILING_TYPES = {"3", "4", "5", "144"}


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _impact_from_text(text: str) -> ThesisImpact:
    lowered = text.lower()
    if _contains_any(lowered, NEGATIVE_TERMS):
        return ThesisImpact.NEGATIVE
    if _contains_any(lowered, POSITIVE_TERMS):
        return ThesisImpact.POSITIVE
    return ThesisImpact.UNKNOWN


def classify_news_event(item: WatchlistItem, news: NewsItem) -> CompanyEvent:
    text = f"{news.title} {news.summary}".lower()
    if "guidance" in text or "outlook" in text:
        category = EventCategory.GUIDANCE
        impact = _impact_from_text(text)
        score = 5 if impact == ThesisImpact.NEGATIVE else 4
    elif "earnings" in text or "results" in text:
        category = EventCategory.EARNINGS
        impact = _impact_from_text(text)
        score = 5
    elif "acquire" in text or "acquisition" in text or "merger" in text:
        category = EventCategory.MNA
        impact = ThesisImpact.UNKNOWN
        score = 4
    elif "contract" in text or "customer" in text:
        category = EventCategory.CUSTOMER_CONTRACT
        impact = _impact_from_text(text)
        score = 4
    elif "lawsuit" in text or "litigation" in text:
        category = EventCategory.LITIGATION
        impact = ThesisImpact.NEGATIVE
        score = 4
    elif "regulation" in text or "regulator" in text:
        category = EventCategory.REGULATION
        impact = _impact_from_text(text)
        score = 4
    else:
        category = EventCategory.NOISE
        impact = ThesisImpact.NEUTRAL
        score = 2

    return CompanyEvent(
        ticker=item.ticker,
        category=category,
        importance_score=score,
        thesis_impact=impact,
        summary=news.summary or news.title,
        evidence=[news.title],
        source_refs=[news.url],
    )


def classify_filing_event(item: WatchlistItem, filing: FilingItem) -> CompanyEvent:
    text = f"{filing.title} {filing.raw_excerpt}".lower()
    filing_type = filing.filing_type.strip().upper()
    if "offering" in text or "convertible" in text or "financing" in text:
        category = EventCategory.FINANCING
        impact = ThesisImpact.UNKNOWN
        score = 4
        summary = filing.title
    elif (
        filing_type in OWNERSHIP_FILING_TYPES
        or "form 3" in text
        or "form 4" in text
        or "form 5" in text
        or "ownership document" in text
    ):
        category = EventCategory.INSIDER_TRANSACTION
        impact = ThesisImpact.NEUTRAL
        score = 2
        summary = (
            f"{filing.title}: ownership/insider filing. "
            "Use related news, if any, for thesis impact."
        )
    elif "8-k" in text or "current report" in text:
        # 8-K is a material event disclosure; content determines impact.
        # Classify as NOISE only as a fallback until the LLM refiner can
        # inspect the actual filing text. Treat importance as medium so it
        # is eligible for LLM refinement rather than being silently dropped.
        category = EventCategory.REGULATION  # placeholder; refiner may override
        impact = _impact_from_text(text)
        score = 3
        summary = filing.title
    else:
        category = EventCategory.NOISE
        impact = ThesisImpact.NEUTRAL
        score = 2
        summary = filing.title

    return CompanyEvent(
        ticker=item.ticker,
        category=category,
        importance_score=score,
        thesis_impact=impact,
        summary=summary,
        evidence=[filing.raw_excerpt or filing.title],
        source_refs=[filing.filing_url],
    )
