from html import escape

from daily_stock_briefing.domain.models import DailyBriefingReport, SymbolBriefing

MAX_TELEGRAM_HTML_LENGTH = 3900


def _format_price(briefing: SymbolBriefing) -> str:
    price = briefing.price_snapshot
    if price is None:
        return "Price: unavailable"
    sign = "+" if price.change_pct >= 0 else ""
    return f"Price: {price.close:.2f} {escape(price.currency)} ({sign}{price.change_pct:.1f}%)"


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
    return f"\n• Sources: {links}"


def render_symbol_line(briefing: SymbolBriefing) -> str:
    ticker = escape(briefing.watchlist_item.ticker)
    name = escape(briefing.watchlist_item.name)
    summary = escape(briefing.thesis_summary)
    questions = " / ".join(
        escape(question) for question in briefing.follow_up_questions[:2]
    )
    question_line = f"\n• Check: {questions}" if questions else ""
    return (
        f"<b>{ticker}</b> {name} ({escape(briefing.priority.value)})\n"
        f"• {_format_price(briefing)}\n"
        f"• Thesis: {summary}"
        f"{question_line}"
        f"{_source_links(briefing)}"
    )


def render_telegram_html(report: DailyBriefingReport) -> str:
    parts = [
        f"<b>Daily Briefing {escape(report.run_date)}</b>",
        escape(report.market_summary),
    ]
    parts.extend(render_symbol_line(briefing) for briefing in report.symbol_briefings)
    rendered = "\n\n".join(parts)
    if len(rendered) <= MAX_TELEGRAM_HTML_LENGTH:
        return rendered
    return rendered[: MAX_TELEGRAM_HTML_LENGTH - 80] + "\n\n<i>Full report attached.</i>"
