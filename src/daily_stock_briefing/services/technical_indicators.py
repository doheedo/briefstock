import math
from collections.abc import Sequence


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


def calculate_rsi(closes: Sequence[float | int | None], period: int = 14) -> float | None:
    if period <= 0:
        raise ValueError("period must be positive")

    clean = _clean_closes(closes)
    if len(clean) < period + 1:
        return None

    window = clean[-(period + 1) :]
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(window, window[1:]):
        delta = current - previous
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    average_gain = sum(gains) / period
    average_loss = sum(losses) / period
    if average_loss == 0 and average_gain > 0:
        return 100.0
    if average_loss == 0 and average_gain == 0:
        return 50.0

    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))
