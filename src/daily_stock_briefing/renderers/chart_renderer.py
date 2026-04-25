import math
import re
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt  # noqa: E402

from daily_stock_briefing.services.technical_indicators import calculate_rsi


def safe_ticker_filename(ticker: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", ticker)
    return safe.strip("._") or "ticker"


def _clean_closes(closes: Sequence[float | int | None]) -> list[float]:
    clean: list[float] = []
    for value in closes:
        try:
            close = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if math.isfinite(close):
            clean.append(close)
    return clean


def _rsi_series(closes: Sequence[float], period: int = 14) -> list[float | None]:
    values: list[float | None] = []
    for index in range(len(closes)):
        values.append(calculate_rsi(closes[: index + 1], period=period))
    return values


def write_price_chart(
    *,
    ticker: str,
    name: str,
    closes: Sequence[float | int | None],
    output_dir: Path,
) -> Path | None:
    clean_closes = _clean_closes(closes)
    if len(clean_closes) < 2:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{safe_ticker_filename(ticker)}.png"
    x_values = list(range(len(clean_closes)))
    rsi_values = _rsi_series(clean_closes)

    try:
        fig, (price_axis, rsi_axis) = plt.subplots(
            2,
            1,
            figsize=(9, 5),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )
        price_axis.plot(x_values, clean_closes, linewidth=1.4)
        price_axis.set_title(f"{ticker} - {name}")
        price_axis.set_ylabel("Close")
        price_axis.grid(True, alpha=0.25)

        rsi_axis.plot(
            x_values,
            [value if value is not None else math.nan for value in rsi_values],
            linewidth=1.0,
        )
        rsi_axis.axhline(30, color="gray", linewidth=0.8, linestyle="--", alpha=0.7)
        rsi_axis.axhline(70, color="gray", linewidth=0.8, linestyle="--", alpha=0.7)
        rsi_axis.set_ylim(0, 100)
        rsi_axis.set_ylabel("RSI(14)")
        rsi_axis.set_xlabel("Trading days")
        rsi_axis.grid(True, alpha=0.25)

        fig.tight_layout()
        fig.savefig(output_path, format="png", dpi=120)
        plt.close(fig)
    except Exception:
        plt.close("all")
        return None
    return output_path
