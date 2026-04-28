"""Tests for research URL builders."""

from daily_stock_briefing.domain.models import WatchlistItem
from daily_stock_briefing.services.research_links import (
    build_research_links,
    yellowbrick_portal_url,
)


def _item(**kwargs: object) -> WatchlistItem:
    defaults = dict(
        ticker="X",
        name="TestCo",
        market="US",
        thesis="t",
        keywords=["k"],
    )
    defaults.update(kwargs)
    return WatchlistItem(**defaults)


def test_google_finance_tsx_suffix_overrides_ca_market() -> None:
    links = build_research_links(_item(ticker="CSU.TO", market="CA"))
    assert links.google_finance is not None
    assert "CSU%3ATSX" in links.google_finance


def test_google_finance_venture_suffix() -> None:
    links = build_research_links(_item(ticker="TOI.V", market="CA"))
    assert links.google_finance is not None
    assert "TOI%3ACVE" in links.google_finance


def test_google_finance_korea_listing_suffix() -> None:
    links = build_research_links(_item(ticker="012700.KQ", market="KR"))
    assert links.google_finance is not None
    assert "012700%3AKRX" in links.google_finance


def test_google_finance_amsterdam_suffix() -> None:
    links = build_research_links(_item(ticker="WKL.AS", market="NL"))
    assert links.google_finance is not None
    assert "WKL%3AAMS" in links.google_finance


def test_yellowbrick_portal_url() -> None:
    assert yellowbrick_portal_url("CSU.TO") == "https://www.joinyellowbrick.com/?ticker=CSU"


def test_yellowbrick_search_in_research_links() -> None:
    links = build_research_links(_item(ticker="RELX", market="US"))
    assert links.yellowbrick_search == "https://www.joinyellowbrick.com/?ticker=RELX"
