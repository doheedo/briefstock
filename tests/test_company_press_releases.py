from daily_stock_briefing.adapters.news.company_press_releases import (
    CompanyPressReleaseProvider,
)
from daily_stock_briefing.domain.enums import EventCategory
from daily_stock_briefing.domain.models import CompanyDisclosure, WatchlistItem
from daily_stock_briefing.renderers.html_report import write_html_report
from daily_stock_briefing.services.report_builder import build_symbol_briefing
from press_release_collector.core.models import PressRelease


def _item() -> WatchlistItem:
    return WatchlistItem(
        ticker="CSU.TO",
        name="Constellation Software",
        market="CA",
        thesis="Track VMS compounding",
        keywords=["Constellation Software"],
        press_release_url="https://www.csisoftware.com/category/press-releases/",
    )


def test_company_press_provider_stores_releases_and_keeps_decks_link_only(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.company_press_releases.collect_html",
        lambda **kwargs: [
            PressRelease.from_raw(
                ticker="CSU.TO",
                company_name="Constellation Software",
                title="Constellation Software Inc. Announces Results for the First Quarter Ended March 31, 2026",
                url="https://www.csisoftware.com/results-q1",
                source_name="csisoftware.com",
                source_type="official_html",
                summary="Total revenue increased 12%.",
            ),
            PressRelease.from_raw(
                ticker="CSU.TO",
                company_name="Constellation Software",
                title="Investor Presentation Deck",
                url="https://www.csisoftware.com/investor-presentation.pdf",
                source_name="csisoftware.com",
                source_type="official_html",
                summary="Do not show this.",
            ),
        ],
    )

    disclosures = CompanyPressReleaseProvider(
        db_path=tmp_path / "press.sqlite"
    ).fetch_disclosures(_item())

    assert [d.kind for d in disclosures] == ["earnings", "ir_deck"]
    assert "Total revenue increased 12%" in disclosures[0].summary
    assert disclosures[1].summary is None


def test_report_builder_turns_earnings_press_release_into_event() -> None:
    item = _item()
    disclosures = [
        CompanyDisclosure(
            kind="earnings",
            title="Constellation Software Announces Results for Q1",
            url="https://www.csisoftware.com/results-q1",
            summary="Revenue increased 12% and operating cash flow improved.",
        ),
        CompanyDisclosure(
            kind="ir_deck",
            title="Investor Presentation Deck",
            url="https://www.csisoftware.com/deck.pdf",
        ),
    ]

    briefing = build_symbol_briefing(item, None, [], [], disclosures)

    assert briefing.company_disclosures == disclosures
    assert briefing.derived_events[0].category == EventCategory.EARNINGS
    assert briefing.derived_events[0].source_refs == [
        "https://www.csisoftware.com/results-q1"
    ]


def test_html_report_renders_press_release_summary_and_deck_link(tmp_path) -> None:
    item = _item()
    briefing = build_symbol_briefing(
        item,
        None,
        [],
        [],
        [
            CompanyDisclosure(
                kind="earnings",
                title="Constellation Software Announces Results for Q1",
                url="https://www.csisoftware.com/results-q1",
                summary="Revenue increased 12% and operating cash flow improved.",
            ),
            CompanyDisclosure(
                kind="ir_deck",
                title="Investor Presentation Deck",
                url="https://www.csisoftware.com/deck.pdf",
            ),
        ],
    )

    from daily_stock_briefing.domain.models import DailyBriefingReport

    path = write_html_report(
        DailyBriefingReport(
            run_date="2026-05-08",
            market_summary="summary",
            symbol_briefings=[briefing],
        ),
        tmp_path / "report.html",
    )

    output = path.read_text(encoding="utf-8")
    assert "기업 홈페이지 공시" in output
    assert "Revenue increased 12%" in output
    assert "Investor Presentation Deck" in output
    assert "https://www.csisoftware.com/deck.pdf" in output
