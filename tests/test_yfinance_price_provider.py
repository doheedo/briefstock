import math

import pytest

from daily_stock_briefing.adapters.prices.yfinance_adapter import YFinancePriceProvider


class _FakeSeries:
    def __init__(self, values: list[object]) -> None:
        self.iloc = values

    def __len__(self) -> int:
        return len(self.iloc)


class _FakeHistory:
    def __init__(self, closes: list[object]) -> None:
        self._closes = _FakeSeries(closes)

    def get(self, key: str):
        return self._closes if key == "Close" else None


def test_yfinance_provider_populates_returns_rsi_and_benchmark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    histories = {
        "LC": [100.0 + index for index in range(252)],
        "^GSPC": [4000.0 + index for index in range(252)],
    }
    calls: list[str] = []

    class _FakeTicker:
        def __init__(self, ticker: str) -> None:
            self.ticker = ticker
            self.info = {"currency": "USD"}

        def history(self, period: str, interval: str):
            calls.append(self.ticker)
            assert period == "1y"
            assert interval == "1d"
            return _FakeHistory(histories[self.ticker])

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        _FakeTicker,
    )

    provider = YFinancePriceProvider()
    snapshot = provider.fetch_daily_snapshot("LC")

    assert snapshot is not None
    assert snapshot.change_pct == pytest.approx((351.0 - 350.0) / 350.0 * 100)
    assert snapshot.return_5d_pct == pytest.approx((351.0 - 346.0) / 346.0 * 100)
    assert snapshot.return_1m_pct == pytest.approx((351.0 - 330.0) / 330.0 * 100)
    assert snapshot.return_1y_pct == pytest.approx((351.0 - 100.0) / 100.0 * 100)
    assert snapshot.benchmark_ticker == "^GSPC"
    assert snapshot.benchmark_return_1y_pct == pytest.approx(
        (4251.0 - 4000.0) / 4000.0 * 100
    )
    assert snapshot.relative_return_1y_pct == pytest.approx(
        snapshot.return_1y_pct - snapshot.benchmark_return_1y_pct
    )
    assert snapshot.rsi_14 is not None
    assert provider.get_cached_closes("LC") == histories["LC"]
    assert calls.count("^GSPC") == 1


def test_yfinance_provider_can_use_kospi200_benchmark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    histories = {
        "207940.KS": [500000.0 + (index * 1000.0) for index in range(252)],
        "^KS200": [400.0 + index for index in range(252)],
    }

    class _FakeTicker:
        def __init__(self, ticker: str) -> None:
            self.ticker = ticker
            self.info = {"currency": "KRW"}

        def history(self, period: str, interval: str):
            return _FakeHistory(histories[self.ticker])

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        _FakeTicker,
    )

    snapshot = YFinancePriceProvider().fetch_daily_snapshot(
        "207940.KS", benchmark_ticker="^KS200"
    )

    assert snapshot is not None
    assert snapshot.benchmark_ticker == "^KS200"
    assert snapshot.currency == "KRW"
    assert snapshot.benchmark_return_1y_pct == pytest.approx(
        (651.0 - 400.0) / 400.0 * 100
    )
    assert snapshot.relative_return_1y_pct == pytest.approx(
        snapshot.return_1y_pct - snapshot.benchmark_return_1y_pct
    )


def test_yfinance_provider_returns_none_when_recent_data_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeTicker:
        info = {"currency": "USD"}

        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, period: str, interval: str):
            return _FakeHistory([100.0, math.nan])

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        _FakeTicker,
    )

    assert YFinancePriceProvider().fetch_daily_snapshot("LC") is None
