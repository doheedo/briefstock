from daily_stock_briefing.services.benchmark_display import benchmark_display_name


def test_benchmark_labels() -> None:
    assert benchmark_display_name("^GSPC") == "S&P 500"
    assert benchmark_display_name("^KS200") == "KOSPI200"
    assert benchmark_display_name(None) == "Benchmark"
