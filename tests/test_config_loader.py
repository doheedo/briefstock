from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_stock_briefing.services.config_loader import load_watchlist


def test_load_watchlist_reads_required_fields() -> None:
    items = load_watchlist(Path("tests/fixtures/sample_watchlist.yaml"))

    assert items[0].ticker == "012700.KQ"
    assert items[0].market == "KR"
    assert items[0].keywords == ["리드코프", "엘씨대부", "배당"]
    assert items[0].source_priority == ["filings", "news", "price"]


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
