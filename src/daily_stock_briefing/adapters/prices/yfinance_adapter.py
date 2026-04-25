import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

import yfinance as yf

from daily_stock_briefing.adapters.prices.base import PriceProvider
from daily_stock_briefing.domain.models import PriceSnapshot
from daily_stock_briefing.services.technical_indicators import calculate_rsi


BENCHMARK_TICKER = "^GSPC"


@dataclass(frozen=True)
class CloseHistory:
    closes: list[float]


class YFinancePriceProvider(PriceProvider):
    def __init__(self, benchmark_ticker: str = BENCHMARK_TICKER) -> None:
        self._benchmark_ticker = benchmark_ticker
        self._history_cache: dict[str, CloseHistory] = {}
        self._benchmark_history: CloseHistory | None = None

    def fetch_daily_snapshot(self, ticker: str) -> PriceSnapshot | None:
        try:
            ticker_data = yf.Ticker(ticker)
            history = ticker_data.history(period="1y", interval="1d")
        except Exception:
            return None

        raw_closes = _series_to_values(history.get("Close"))
        if len(raw_closes) < 2:
            return None

        previous_close = _coerce_close(raw_closes[-2])
        close = _coerce_close(raw_closes[-1])
        if previous_close is None or close is None:
            return None
        if not math.isfinite(previous_close) or not math.isfinite(close):
            return None
        closes = _finite_closes(raw_closes)
        if len(closes) < 2:
            return None
        self._history_cache[ticker] = CloseHistory(closes=closes)

        change = close - previous_close
        change_pct = 0.0 if previous_close == 0 else (change / previous_close) * 100
        currency = "USD"
        try:
            info = getattr(ticker_data, "info", None)
        except Exception:
            info = None
        if isinstance(info, dict):
            metadata_currency = info.get("currency")
            if isinstance(metadata_currency, str):
                metadata_currency = metadata_currency.strip()
                if metadata_currency:
                    currency = metadata_currency
        benchmark_return_1y_pct = self._benchmark_return_1y_pct()
        return_1y_pct = _return_from_offset(closes, len(closes) - 1)

        return PriceSnapshot(
            ticker=ticker,
            previous_close=previous_close,
            close=close,
            change=change,
            change_pct=change_pct,
            currency=currency,
            as_of=datetime.now(timezone.utc),
            source="yfinance",
            return_5d_pct=_return_from_offset(closes, 5),
            return_1m_pct=_return_from_offset(closes, 21),
            return_1y_pct=return_1y_pct,
            benchmark_ticker=self._benchmark_ticker,
            benchmark_return_1y_pct=benchmark_return_1y_pct,
            relative_return_1y_pct=(
                return_1y_pct - benchmark_return_1y_pct
                if return_1y_pct is not None and benchmark_return_1y_pct is not None
                else None
            ),
            rsi_14=calculate_rsi(closes, period=14),
        )

    def get_cached_closes(self, ticker: str) -> list[float] | None:
        history = self._history_cache.get(ticker)
        return list(history.closes) if history else None

    def _benchmark_return_1y_pct(self) -> float | None:
        if self._benchmark_history is None:
            try:
                benchmark_data = yf.Ticker(self._benchmark_ticker)
                history = benchmark_data.history(period="1y", interval="1d")
            except Exception:
                self._benchmark_history = CloseHistory(closes=[])
            else:
                self._benchmark_history = CloseHistory(
                    closes=_finite_closes(_series_to_values(history.get("Close")))
                )
        if len(self._benchmark_history.closes) < 2:
            return None
        return _return_from_offset(
            self._benchmark_history.closes,
            len(self._benchmark_history.closes) - 1,
        )


def _coerce_close(value: object) -> float | None:
    try:
        close = float(value)
    except (TypeError, ValueError):
        return None
    return close if math.isfinite(close) else None


def _series_to_values(series: object) -> list[object]:
    if series is None:
        return []
    tolist = getattr(series, "tolist", None)
    if callable(tolist):
        values = tolist()
        return list(values) if isinstance(values, Sequence) else []
    iloc = getattr(series, "iloc", None)
    if iloc is not None:
        return list(iloc)
    try:
        return list(series)  # type: ignore[arg-type]
    except TypeError:
        return []


def _finite_closes(values: Sequence[object]) -> list[float]:
    closes: list[float] = []
    for value in values:
        close = _coerce_close(value)
        if close is not None:
            closes.append(close)
    return closes


def _return_from_offset(closes: Sequence[float], offset: int) -> float | None:
    if len(closes) < offset + 1:
        return None
    start = closes[-(offset + 1)]
    end = closes[-1]
    if start == 0:
        return None
    return ((end - start) / start) * 100
