"""Attach Yellowbrick pitch summaries to symbol briefings."""

from __future__ import annotations

from daily_stock_briefing.adapters.llm.openai_compatible import OpenAICompatibleLlmClassifier
from daily_stock_briefing.adapters.yellowbrick.readability_extract import extract_readable_text
from daily_stock_briefing.adapters.yellowbrick.supabase_pitch import fetch_latest_pitch_row
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
        row = fetch_latest_pitch_row(base, days=30)
    except Exception as exc:
        section.error = f"Yellowbrick 데이터 조회 실패: {exc}"
        return briefing.model_copy(update={"yellowbrick_pitch": section})

    if row is None:
        return briefing.model_copy(
            update={
                "yellowbrick_pitch": section.model_copy(
                    update={
                        "summary_ko": "최근 30일 내 해당 티커의 Yellowbrick 피칭 레코드가 없습니다.",
                    }
                )
            }
        )

    title = row.get("title")
    title_str = title if isinstance(title, str) else None
    raw_url = row.get("url")
    section.article_url = raw_url if isinstance(raw_url, str) else None
    d = row.get("date_original")
    section.pitch_date = d if isinstance(d, str) else None

    summary_short = row.get("summary_short")
    summary_long = row.get("summary_paragraph")
    db_excerpt = ""
    if isinstance(summary_long, str) and summary_long.strip():
        db_excerpt = summary_long.strip()
    elif isinstance(summary_short, str) and summary_short.strip():
        db_excerpt = summary_short.strip()
    section.source_excerpt_en = db_excerpt or None

    summary_ko: str | None = None
    body_for_llm = ""
    if section.article_url:
        body_for_llm = extract_readable_text(section.article_url)
    if not body_for_llm.strip() and db_excerpt:
        body_for_llm = db_excerpt

    if llm is not None and body_for_llm.strip():
        summary_ko = llm.summarize_yellowbrick_pitch(
            body_for_llm,
            title=title_str,
        )
    if not summary_ko and db_excerpt:
        summary_ko = (
            "[자동 요약 비활성/실패] DB 요약(영문): "
            + (db_excerpt[:800] + ("…" if len(db_excerpt) > 800 else ""))
        )
    elif not summary_ko:
        summary_ko = "본문을 가져오지 못했습니다. 원문 링크를 확인하세요."

    section.summary_ko = summary_ko
    return briefing.model_copy(update={"yellowbrick_pitch": section})
