from datetime import datetime, timezone

from daily_stock_briefing.domain.enums import DailyPriority
from daily_stock_briefing.domain.models import (
    DailyBriefingReport,
    PriceSnapshot,
    SymbolBriefing,
    WatchlistItem,
)
from daily_stock_briefing.renderers.html_report import write_html_report
from daily_stock_briefing.renderers.telegram_html import (
    render_symbol_line,
    render_telegram_html,
)


def _briefing() -> SymbolBriefing:
    return SymbolBriefing(
        watchlist_item=WatchlistItem(
            ticker="SNOW",
            name="Snowflake",
            market="US",
            thesis="data platform moat",
            keywords=["Snowflake"],
            source_priority=["news", "filings", "price"],
        ),
        price_snapshot=PriceSnapshot(
            ticker="SNOW",
            previous_close=100.0,
            close=104.0,
            change=4.0,
            change_pct=4.0,
            currency="USD",
            as_of=datetime(2026, 4, 24, tzinfo=timezone.utc),
            source="yfinance",
        ),
        thesis_summary="negative: growth slowdown",
        follow_up_questions=["Does usage reaccelerate next quarter?"],
        priority=DailyPriority.HIGH,
    )


def test_render_symbol_line_uses_only_supported_tags() -> None:
    html = render_symbol_line(_briefing())

    assert "<b>SNOW</b>" in html
    assert "Price: 104.00 USD (+4.0%)" in html
    for unsupported in ("<ul>", "<li>", "<table>", "<style>", "<script>"):
        assert unsupported not in html


def test_render_telegram_html_escapes_user_text() -> None:
    report = DailyBriefingReport(
        run_date="2026-04-24",
        market_summary="Market <mixed>",
        symbol_briefings=[_briefing()],
    )

    html = render_telegram_html(report)

    assert "<b>Daily Briefing 2026-04-24</b>" in html
    assert "Market &lt;mixed&gt;" in html
    assert "<table>" not in html


def test_write_html_report_creates_full_report(tmp_path) -> None:
    report = DailyBriefingReport(
        run_date="2026-04-24",
        market_summary="Minimal market summary",
        symbol_briefings=[_briefing()],
    )

    path = write_html_report(report, tmp_path / "reports" / "html" / "2026-04-24.html")

    output = path.read_text(encoding="utf-8")
    assert "<!doctype html>" in output
    assert "Daily Stock Briefing - 2026-04-24" in output
    assert "SNOW - Snowflake" in output
    assert "negative: growth slowdown" in output
