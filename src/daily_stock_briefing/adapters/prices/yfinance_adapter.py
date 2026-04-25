import math
from datetime import datetime, timezone

import yfinance as yf

from daily_stock_briefing.adapters.prices.base import PriceProvider
from daily_stock_briefing.domain.models import PriceSnapshot


class YFinancePriceProvider(PriceProvider):
    def fetch_daily_snapshot(self, ticker: str) -> PriceSnapshot | None:
        try:
            ticker_data = yf.Ticker(ticker)
            history = ticker_data.history(period="2d", interval="1d")
        except Exception:
            return None

        closes = history.get("Close")
        if closes is None or len(closes) < 2:
            return None

        previous_close = _coerce_close(closes.iloc[-2])
        close = _coerce_close(closes.iloc[-1])
        if previous_close is None or close is None:
            return None
        if not math.isfinite(previous_close) or not math.isfinite(close):
            return None
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

        return PriceSnapshot(
            ticker=ticker,
            previous_close=previous_close,
            close=close,
            change=change,
            change_pct=change_pct,
            currency=currency,
            as_of=datetime.now(timezone.utc),
            source="yfinance",
        )


def _coerce_close(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
