import base64
from datetime import datetime, timezone

from daily_stock_briefing.domain.enums import DailyPriority, EventCategory, ThesisImpact
from daily_stock_briefing.domain.models import (
    CompanyEvent,
    DailyBriefingReport,
    PriceSnapshot,
    SymbolBriefing,
    WatchlistItem,
    CompanyDisclosure,
    WagnHoldingChange,
    WagnHoldingItem,
    WagnHoldingsSection,
)
from daily_stock_briefing.renderers.html_report import write_html_report
from daily_stock_briefing.renderers.telegram_html import (
    MAX_TELEGRAM_HTML_LENGTH,
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
        return_5d_pct=-3.4,
        return_1m_pct=2.1,
        return_1y_pct=-18.4,
        benchmark_return_1y_pct=11.2,
        relative_return_1y_pct=-29.6,
        rsi_14=37.8,
        chart_path="../charts/2026-04-24/SNOW.png",
    ),
        thesis_summary="negative: growth slowdown",
        follow_up_questions=["Does usage reaccelerate next quarter?"],
        priority=DailyPriority.HIGH,
        derived_events=[
            CompanyEvent(
                ticker="SNOW",
                category=EventCategory.GUIDANCE,
                importance_score=5,
                thesis_impact=ThesisImpact.NEGATIVE,
                summary="Growth slowdown",
                evidence=["Guidance lowered"],
                source_refs=["https://example.com/source?x=1&y=2"],
            )
        ],
    )


def test_render_symbol_line_uses_only_supported_tags() -> None:
    html = render_symbol_line(_briefing())

    assert "<b>SNOW</b>" in html
    assert "가격: 104.00 USD (+4.0%)" in html
    assert (
        "5D: -3.4% / 1M: +2.1% / 1Y: -18.4% / "
        "S&amp;P 500 1Y: +11.2% / Relative: -29.6%p / RSI(14): 37.8"
    ) in html
    assert "Relative: -29.6%p\n• RSI(14)" not in html
    assert '<a href="https://example.com/source?x=1&amp;y=2">1</a>' in html
    for unsupported in ("<ul>", "<li>", "<table>", "<style>", "<script>"):
        assert unsupported not in html


def test_render_symbol_line_includes_company_homepage_links_without_deck_summary() -> None:
    briefing = _briefing().model_copy(
        update={
            "company_disclosures": [
                CompanyDisclosure(
                    kind="earnings",
                    title="Snowflake Announces Results",
                    url="https://example.com/results",
                    summary="Revenue increased 10%.",
                ),
                CompanyDisclosure(
                    kind="ir_deck",
                    title="Investor Presentation Deck",
                    url="https://example.com/deck.pdf",
                ),
            ]
        }
    )

    html = render_symbol_line(briefing)

    assert "기업홈:" in html
    assert '<a href="https://example.com/results">실적</a>' in html
    assert '<a href="https://example.com/deck.pdf">IR덱</a>' in html
    assert "Revenue increased 10%" not in html


def test_render_telegram_html_escapes_user_text() -> None:
    report = DailyBriefingReport(
        run_date="2026-04-24",
        market_summary="Market <mixed>",
        symbol_briefings=[_briefing()],
    )

    html = render_telegram_html(report)

    assert "<b>데일리 브리핑 2026-04-24</b>" in html
    assert "Market &lt;mixed&gt;" in html
    assert "<table>" not in html


def test_render_telegram_html_truncates_without_breaking_html_tags() -> None:
    briefing = _briefing().model_copy(
        update={
            "thesis_summary": "x" * (MAX_TELEGRAM_HTML_LENGTH + 100),
            "follow_up_questions": [],
        }
    )
    report = DailyBriefingReport(
        run_date="2026-04-24",
        market_summary="Daily delta briefing generated from watchlist sources.",
        symbol_briefings=[briefing],
    )

    html = render_telegram_html(report)

    assert len(html) <= MAX_TELEGRAM_HTML_LENGTH
    assert html.endswith("<i>전체 리포트 첨부.</i>")
    assert "Thesis 영향:" not in html
    assert "<a href=" not in html


def test_write_html_report_creates_full_report(tmp_path) -> None:
    chart_path = tmp_path / "reports" / "charts" / "2026-04-24" / "SNOW.png"
    chart_path.parent.mkdir(parents=True)
    chart_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-png")
    report = DailyBriefingReport(
        run_date="2026-04-24",
        market_summary="Minimal market summary",
        symbol_briefings=[_briefing()],
    )

    path = write_html_report(report, tmp_path / "reports" / "html" / "2026-04-24.html")

    output = path.read_text(encoding="utf-8")
    assert "<!doctype html>" in output
    assert "데일리 종목 브리핑 - 2026-04-24" in output
    assert "SNOW - Snowflake" in output
    assert "negative: growth slowdown" in output
    assert "RSI(14): 37.8" in output
    assert 'class="chart"' in output
    expected_chart_src = (
        "data:image/png;base64,"
        + base64.b64encode(chart_path.read_bytes()).decode("ascii")
    )
    assert f'src="{expected_chart_src}"' in output
    assert 'href="https://example.com/source?x=1&amp;y=2"' in output


def test_write_html_report_compacts_metrics_events_and_wagn_table(tmp_path) -> None:
    report = DailyBriefingReport(
        run_date="2026-04-24",
        market_summary="Minimal market summary",
        symbol_briefings=[_briefing()],
        wagn_holdings=WagnHoldingsSection(
            as_of_date="04/24/2026",
            source_url="https://example.com/wagn",
            download_url="https://example.com/wagn.csv",
            total_holdings=2,
            top_holdings=[
                WagnHoldingItem(ticker="AAA", name="A Co", weight_pct=10.0),
                WagnHoldingItem(ticker="BBB", name="B Co", weight_pct=5.0),
            ],
            notable_changes=[
                WagnHoldingChange(
                    ticker="AAA",
                    name="A Co",
                    previous_weight_pct=8.5,
                    current_weight_pct=10.0,
                    delta_pct=1.5,
                    change_type="weight_changed",
                )
            ],
        ),
    )

    path = write_html_report(report, tmp_path / "reports" / "html" / "2026-04-24.html")

    output = path.read_text(encoding="utf-8")
    assert "<table" in output
    assert "AAA" in output
    assert "+1.5%p" in output
    assert "BBB" in output
    assert "5D: -3.4% / 1M: +2.1% / 1Y: -18.4% / S&amp;P 500 1Y: +11.2% / Relative: -29.6%p / RSI(14): 37.8" in output
    assert "5D: -3.4% /" in output
    assert "<br>" not in output
    assert "<strong>guidance</strong> / score 5 / negative: Growth slowdown" in output
