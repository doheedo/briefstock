import math

import pytest

from daily_stock_briefing.services.technical_indicators import calculate_rsi


def test_calculate_rsi_returns_float_for_mixed_moves() -> None:
    closes = [44, 45, 44, 46, 47, 46, 48, 49, 47, 48, 50, 49, 51, 52, 50]

    rsi = calculate_rsi(closes)

    assert isinstance(rsi, float)
    assert 0 < rsi < 100


def test_calculate_rsi_returns_none_when_data_is_short() -> None:
    assert calculate_rsi([1, 2, 3], period=14) is None


def test_calculate_rsi_returns_100_when_there_are_no_losses() -> None:
    assert calculate_rsi(list(range(1, 16)), period=14) == 100.0


def test_calculate_rsi_returns_50_when_prices_are_flat() -> None:
    assert calculate_rsi([10.0] * 15, period=14) == 50.0


def test_calculate_rsi_ignores_nan_and_invalid_values_safely() -> None:
    closes = [1, 2, math.nan, None, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

    assert calculate_rsi(closes, period=14) is None
    assert calculate_rsi([1, 2, math.nan, 3, 4, 5], period=3) == pytest.approx(100.0)
