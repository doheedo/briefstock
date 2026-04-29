"""Attach Yellowbrick pitch summaries to symbol briefings."""

from __future__ import annotations

from daily_stock_briefing.adapters.llm.openai_compatible import OpenAICompatibleLlmClassifier
from daily_stock_briefing.adapters.yellowbrick.readability_extract import (
    extract_readable_text,
    find_recent_read_more_candidate,
)
from daily_stock_briefing.domain.models import SymbolBriefing, YellowbrickPitchSection
from daily_stock_briefing.services.research_links import yellowbrick_portal_url


def _base_ticker(ticker: str) -> str:
    return ticker.split(".")[0]


def enrich_symbol_with_yellowbrick(
    briefing: SymbolBriefing,
    llm: OpenAICompatibleLlmClassifier | None,
) -> SymbolBriefing:
    item = briefing.watchlist_item
    search_url = yellowbrick_portal_url(item.ticker) or ""
    base = _base_ticker(item.ticker)

    section = YellowbrickPitchSection(search_url=search_url)

    try:
        candidate = find_recent_read_more_candidate(base, days=30)
    except Exception as exc:
        section.error = f"Yellowbrick listing 조회 실패: {exc}"
        return briefing.model_copy(update={"yellowbrick_pitch": section})

    if candidate is None:
        return briefing.model_copy(
            update={
                "yellowbrick_pitch": section.model_copy(
                    update={
                        "summary_ko": "최근 30일 내 해당 티커의 Yellowbrick Read full article 항목이 없습니다.",
                    }
                )
            }
        )

    section.article_url = candidate.read_more_url
    section.pitch_date = candidate.pitch_date

    summary_ko: str | None = None
    body_for_llm = extract_readable_text(candidate.read_more_url)
    section.source_excerpt_en = body_for_llm[:1200] if body_for_llm else None

    if llm is not None and body_for_llm.strip():
        summary_ko = llm.summarize_yellowbrick_pitch(
            body_for_llm,
            title=briefing.watchlist_item.name,
        )

    if not summary_ko and body_for_llm:
        summary_ko = body_for_llm[:800] + ("…" if len(body_for_llm) > 800 else "")
    elif not summary_ko:
        summary_ko = "Read full article 본문 추출에 실패했습니다. 원문 링크를 확인하세요."

    section.summary_ko = summary_ko
    return briefing.model_copy(update={"yellowbrick_pitch": section})
