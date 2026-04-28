from html import escape

from daily_stock_briefing.domain.models import DailyBriefingReport, SymbolBriefing
from daily_stock_briefing.services.benchmark_display import benchmark_display_name

MAX_TELEGRAM_HTML_LENGTH = 3900
FULL_REPORT_NOTE = "<i>전체 리포트 첨부.</i>"


def _priority_label(value: str) -> str:
    return {"High": "높음", "Medium": "중간", "Low": "낮음"}.get(value, value)


def _format_price(briefing: SymbolBriefing) -> str:
    price = briefing.price_snapshot
    if price is None:
        return "가격: n/a"
    sign = "+" if price.change_pct >= 0 else ""
    return f"가격: {price.close:.2f} {escape(price.currency)} ({sign}{price.change_pct:.1f}%)"


def _format_pct(value: float | None, *, suffix: str = "%") -> str:
    return "n/a" if value is None else f"{value:+.1f}{suffix}"


def _format_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _format_metrics(briefing: SymbolBriefing) -> str:
    price = briefing.price_snapshot
    bench = escape(benchmark_display_name(price.benchmark_ticker if price else None))
    if price is None:
        return (
            "\n• 5D: n/a / 1M: n/a / 1Y: n/a\n"
            f"• {bench} 1Y: n/a / Relative: n/a\n• RSI(14): n/a"
        )
    return (
        f"\n• 5D: {_format_pct(price.return_5d_pct)} / "
        f"1M: {_format_pct(price.return_1m_pct)} / "
        f"1Y: {_format_pct(price.return_1y_pct)}"
        f"\n• {bench} 1Y: {_format_pct(price.benchmark_return_1y_pct)} / "
        f"Relative: {_format_pct(price.relative_return_1y_pct, suffix='%p')}"
        f"\n• RSI(14): {_format_number(price.rsi_14)}"
    )


def _source_links(briefing: SymbolBriefing) -> str:
    urls: list[str] = []
    for event in briefing.derived_events:
        for url in event.source_refs:
            if url and url not in urls:
                urls.append(url)
    if not urls:
        return ""
    links = " ".join(
        f'<a href="{escape(url, quote=True)}">{index}</a>'
        for index, url in enumerate(urls[:3], start=1)
    )
    return f"\n• 출처: {links}"


def render_symbol_line(briefing: SymbolBriefing) -> str:
    ticker = escape(briefing.watchlist_item.ticker)
    name = escape(briefing.watchlist_item.name)
    summary = escape(briefing.thesis_summary)
    questions = " / ".join(
        escape(question) for question in briefing.follow_up_questions[:2]
    )
    question_line = f"\n• 확인: {questions}" if questions else ""
    return (
        f"<b>{ticker}</b> {name} ({escape(_priority_label(briefing.priority.value))})\n"
        f"• {_format_price(briefing)}\n"
        f"{_format_metrics(briefing)}\n"
        f"• Thesis 영향: {summary}"
        f"{question_line}"
        f"{_source_links(briefing)}"
    )


def render_telegram_html(report: DailyBriefingReport) -> str:
    parts = [
        f"<b>데일리 브리핑 {escape(report.run_date)}</b>",
        escape(report.market_summary),
    ]
    note_suffix = f"\n\n{FULL_REPORT_NOTE}"
    truncated = False

    for briefing in report.symbol_briefings:
        candidate_parts = [*parts, render_symbol_line(briefing)]
        candidate = "\n\n".join(candidate_parts)
        if len(candidate) + len(note_suffix) > MAX_TELEGRAM_HTML_LENGTH:
            truncated = True
            break
        parts = candidate_parts

    rendered = "\n\n".join(parts)
    if truncated:
        return rendered + note_suffix
    return rendered
