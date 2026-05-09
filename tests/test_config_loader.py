from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_stock_briefing.services.config_loader import load_watchlist


def test_load_watchlist_reads_required_fields() -> None:
    items = load_watchlist(Path("tests/fixtures/sample_watchlist.yaml"))

    assert items[0].ticker == "012700.KQ"
    assert items[0].market == "KR"
    assert items[0].group == "kr_bio"
    assert items[0].keywords == ["리드코프", "엘씨대부", "배당"]
    assert items[0].source_priority == ["filings", "news", "price"]


def test_project_watchlist_includes_requested_us_and_india_adrs() -> None:
    items = load_watchlist(Path("config/watchlist.yaml"))
    by_ticker = {item.ticker: item for item in items}

    assert by_ticker["Z"].name == "Zillow Group, Inc. Class C"
    assert by_ticker["RBLX"].name == "Roblox Corporation"
    assert by_ticker["HDB"].name == "HDFC Bank Limited ADR"
    assert by_ticker["IBN"].name == "ICICI Bank Limited ADR"
    assert by_ticker["HDB"].market == "US"
    assert by_ticker["IBN"].market == "US"


def test_project_watchlist_includes_csu_press_release_url() -> None:
    items = load_watchlist(Path("config/watchlist.yaml"))
    by_ticker = {item.ticker: item for item in items}

    assert (
        by_ticker["CSU.TO"].press_release_url
        == "https://www.csisoftware.com/category/press-releases/"
    )
    assert (
        by_ticker["Z"].press_release_url
        == "https://zillowgroup.mediaroom.com/press-releases"
    )
    assert by_ticker["RBLX"].press_release_url == "https://about.roblox.com/newsroom"
    assert (
        by_ticker["HDB"].press_release_url
        == "https://www.hdfc.bank.in/about-us/investor-relations/financial-results"
    )
    assert (
        by_ticker["IBN"].press_release_url
        == "https://www.icici.bank.in/about-us/invest-relations"
    )
    assert (
        by_ticker["TRI"].press_release_url
        == "https://ir.thomsonreuters.com/news-and-events/press-releases"
    )
    assert (
        by_ticker["WLK"].press_release_url
        == "https://investors.westlake.com/news-events/news-releases"
    )
    assert (
        by_ticker["UPST"].press_release_url
        == "https://ir.upstart.com/news-and-events/news-releases"
    )
    assert by_ticker["TME"].press_release_url == "https://ir.tencentmusic.com/Press-Releases"
    assert (
        by_ticker["VFC"].press_release_url
        == "https://www.vfc.com/investors/news-events-presentations/press-releases"
    )
    assert by_ticker["KSPI"].press_release_url == "https://ir.kaspi.kz/news/"
    assert by_ticker["UMG.AS"].press_release_url == "https://www.universalmusic.com/news/"


def test_load_watchlist_defaults_source_priority_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        "\n".join(
            [
                "watchlist:",
                "  - ticker: LC",
                "    name: LendingClub",
                "    market: US",
                "    thesis: funding resilience",
                "    keywords: [LendingClub]",
            ]
        ),
        encoding="utf-8",
    )

    items = load_watchlist(path)

    assert items[0].source_priority == ["filings", "news", "price"]
    assert items[0].group == "default"


def test_load_watchlist_rejects_invalid_shape(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.yaml"
    path.write_text("watchlist:\n  ticker: LC\n", encoding="utf-8")

    with pytest.raises(ValueError, match="watchlist must be a list"):
        load_watchlist(path)


def test_load_watchlist_rejects_empty_keywords(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        "\n".join(
            [
                "watchlist:",
                "  - ticker: LC",
                "    name: LendingClub",
                "    market: US",
                "    thesis: funding resilience",
                "    keywords: []",
                "    source_priority: [news]",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_watchlist(path)


def test_load_watchlist_rejects_unknown_source_priority(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        "\n".join(
            [
                "watchlist:",
                "  - ticker: LC",
                "    name: LendingClub",
                "    market: US",
                "    thesis: funding resilience",
                "    keywords: [LendingClub]",
                "    source_priority: [blog]",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_watchlist(path)


def test_load_watchlist_rejects_duplicate_source_priority(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        "\n".join(
            [
                "watchlist:",
                "  - ticker: LC",
                "    name: LendingClub",
                "    market: US",
                "    thesis: funding resilience",
                "    keywords: [LendingClub]",
                "    source_priority: [news, filings, news]",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_watchlist(path)
