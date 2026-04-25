from datetime import datetime, timezone

from daily_stock_briefing.domain.models import PriceSnapshot


def test_price_snapshot_extended_fields_are_backward_compatible() -> None:
    snapshot = PriceSnapshot(
        ticker="SNOW",
        previous_close=100.0,
        close=101.0,
        change=1.0,
        change_pct=1.0,
        currency="USD",
        as_of=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source="test",
    )

    assert snapshot.return_5d_pct is None
    assert snapshot.rsi_14 is None
    assert snapshot.benchmark_ticker == "^GSPC"
    assert snapshot.chart_path is None
