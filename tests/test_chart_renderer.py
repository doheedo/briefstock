from pathlib import Path

from daily_stock_briefing.renderers.chart_renderer import (
    safe_ticker_filename,
    write_price_chart,
)


def test_write_price_chart_creates_png(tmp_path: Path) -> None:
    path = write_price_chart(
        ticker="SNOW",
        name="Snowflake",
        closes=[100 + index for index in range(40)],
        output_dir=tmp_path / "charts",
    )

    assert path is not None
    assert path.exists()
    assert path.read_bytes().startswith(b"\x89PNG")


def test_write_price_chart_returns_none_when_data_is_insufficient(tmp_path: Path) -> None:
    assert (
        write_price_chart(
            ticker="SNOW",
            name="Snowflake",
            closes=[100.0],
            output_dir=tmp_path / "charts",
        )
        is None
    )


def test_safe_ticker_filename_replaces_path_separators() -> None:
    assert safe_ticker_filename("ABC/DEF") == "ABC_DEF"
