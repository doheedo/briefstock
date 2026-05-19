from daily_stock_briefing.adapters.news.company_press_releases import (
    CompanyPressReleaseProvider,
    find_pdf_press_release_summary,
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
                title="Constellation Software Announces Acquisition",
                url="https://www.csisoftware.com/acquisition",
                source_name="csisoftware.com",
                source_type="official_html",
                summary="The company agreed to acquire a vertical market software business.",
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
            PressRelease.from_raw(
                ticker="CSU.TO",
                company_name="Constellation Software",
                title="Q4FY26 Earnings Presentation",
                url="https://www.csisoftware.com/q4fy26-earnings-presentation.pdf",
                source_name="csisoftware.com",
                source_type="official_html",
                summary="Do not show this either.",
            ),
        ],
    )

    disclosures = CompanyPressReleaseProvider(
        db_path=tmp_path / "press.sqlite"
    ).fetch_disclosures(_item())

    assert [d.kind for d in disclosures] == [
        "earnings",
        "press_release",
        "ir_deck",
        "ir_deck",
    ]
    assert "Total revenue increased 12%" in disclosures[0].summary
    assert "vertical market software" in disclosures[1].summary
    assert disclosures[2].summary is None
    assert disclosures[3].summary is None


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


def test_company_press_provider_classifies_reports_quarter_results_as_earnings(
    tmp_path,
    monkeypatch,
) -> None:
    item = _item().model_copy(update={"press_release_url": "https://example.com/news"})
    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.company_press_releases.collect_html",
        lambda **kwargs: [
            PressRelease.from_raw(
                ticker="META",
                company_name="Meta Platforms",
                title="Meta Reports First Quarter 2026 Results",
                url="https://investor.atmeta.com/results",
                source_name="investor.atmeta.com",
                source_type="official_html",
            )
        ],
    )

    disclosures = CompanyPressReleaseProvider(
        db_path=tmp_path / "press.sqlite"
    ).fetch_disclosures(item)

    assert disclosures[0].kind == "earnings"


def test_company_press_provider_classifies_announces_quarter_results_as_earnings(
    tmp_path,
    monkeypatch,
) -> None:
    item = _item().model_copy(update={"press_release_url": "https://example.com/news"})
    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.company_press_releases.collect_html",
        lambda **kwargs: [
            PressRelease.from_raw(
                ticker="AMZN",
                company_name="Amazon.com",
                title="Amazon.com Announces First Quarter Results",
                url="https://ir.aboutamazon.com/results",
                source_name="ir.aboutamazon.com",
                source_type="official_html",
            )
        ],
    )

    disclosures = CompanyPressReleaseProvider(
        db_path=tmp_path / "press.sqlite"
    ).fetch_disclosures(item)

    assert disclosures[0].kind == "earnings"


def test_company_press_provider_uses_rss_urls(tmp_path, monkeypatch) -> None:
    item = _item().model_copy(
        update={"ticker": "UBER", "press_release_url": "https://investor.uber.com/rss/PressRelease.aspx"}
    )
    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.company_press_releases.collect_rss",
        lambda ticker, company_name, url: [
            PressRelease.from_raw(
                ticker=ticker,
                company_name=company_name,
                title="Uber Announces Results for First Quarter 2026",
                url="https://investor.uber.com/news/results",
                source_name=url,
                source_type="official_rss",
            )
        ],
    )

    disclosures = CompanyPressReleaseProvider(
        db_path=tmp_path / "press.sqlite"
    ).fetch_disclosures(item)

    assert disclosures[0].kind == "earnings"
    assert disclosures[0].title == "Uber Announces Results for First Quarter 2026"


def test_company_press_provider_uses_sec_atom_urls(tmp_path, monkeypatch) -> None:
    item = _item().model_copy(
        update={
            "ticker": "GOOG",
            "press_release_url": (
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                "&CIK=GOOG&type=8-K&output=atom"
            ),
        }
    )
    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.company_press_releases.collect_rss",
        lambda ticker, company_name, url: [
            PressRelease.from_raw(
                ticker=ticker,
                company_name=company_name,
                title="8-K - Current report",
                url="https://www.sec.gov/Archives/edgar/data/1652044/report.html",
                source_name=url,
                source_type="official_rss",
            )
        ],
    )

    disclosures = CompanyPressReleaseProvider(
        db_path=tmp_path / "press.sqlite"
    ).fetch_disclosures(item)

    assert disclosures[0].title == "8-K - Current report"


def test_company_press_provider_uses_nasdaq_press_release_urls(
    tmp_path,
    monkeypatch,
) -> None:
    item = _item().model_copy(
        update={
            "ticker": "SABR",
            "name": "Sabre Corporation",
            "press_release_url": "https://www.nasdaq.com/market-activity/stocks/sabr/press-releases",
        }
    )
    seen = {}

    def _collect_nasdaq(ticker, company_name, max_items=6):
        seen["args"] = (ticker, company_name, max_items)
        return []

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.company_press_releases.collect_nasdaq_press_releases",
        _collect_nasdaq,
    )

    CompanyPressReleaseProvider(db_path=tmp_path / "press.sqlite").fetch_disclosures(item)

    assert seen["args"] == ("SABR", "Sabre Corporation", 6)


def test_company_press_provider_enriches_pdf_summary_from_wire_context(
    tmp_path,
    monkeypatch,
) -> None:
    item = _item().model_copy(update={"press_release_url": "https://example.com/news"})
    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.company_press_releases.collect_html",
        lambda **kwargs: [
            PressRelease.from_raw(
                ticker="BFF.MI",
                company_name="BFF Bank",
                title="BFF Bank Board Approves Annual Report",
                url="https://example.com/press-release.pdf",
                source_name="example.com",
                source_type="official_html",
            )
        ],
    )
    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.company_press_releases.find_pdf_press_release_summary",
        lambda release: "BFF Bank said the board approved the annual report and dividend proposal.",
    )

    disclosures = CompanyPressReleaseProvider(
        db_path=tmp_path / "press.sqlite"
    ).fetch_disclosures(item)

    assert disclosures[0].summary == (
        "BFF Bank said the board approved the annual report and dividend proposal."
    )


def test_pdf_summary_search_falls_back_to_general_news(monkeypatch) -> None:
    release = PressRelease.from_raw(
        ticker="KSPI",
        company_name="Kaspi.kz",
        title="1Q 2026 Results",
        url="https://ir.kaspi.kz/media/1Q_2026_Results.pdf",
        source_name="ir.kaspi.kz",
        source_type="official_html",
    )
    calls: list[str] = []

    def _collect_rss(ticker, company_name, url, extra_noise_terms=()):
        calls.append(url)
        if len(calls) == 1:
            return []
        return [
            PressRelease.from_raw(
                ticker=ticker,
                company_name=company_name,
                title="Kaspi.kz reports first-quarter 2026 results",
                url="https://news.example.com/kaspi-q1",
                source_name="news.example.com",
                source_type="official_rss",
                summary="Kaspi.kz reported first-quarter growth across payments and marketplace activity.",
            )
        ]

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.company_press_releases.collect_rss",
        _collect_rss,
    )

    summary = find_pdf_press_release_summary(release)

    assert summary == (
        "Kaspi.kz reported first-quarter growth across payments and marketplace activity."
    )
    assert len(calls) == 2
    assert "globenewswire+or+prnewswire+or+businesswire" in calls[0].lower()


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
                kind="press_release",
                title="Constellation Software Announces Acquisition",
                url="https://www.csisoftware.com/acquisition",
                summary="The company agreed to acquire a vertical market software business.",
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
    assert "vertical market software business" in output
    assert "Investor Presentation Deck" in output
    assert "https://www.csisoftware.com/deck.pdf" in output
