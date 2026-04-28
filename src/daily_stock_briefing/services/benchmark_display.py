"""Human-readable labels for benchmark index tickers used in reports."""


def benchmark_display_name(benchmark_ticker: str | None) -> str:
    if not benchmark_ticker:
        return "Benchmark"
    mapping = {
        "^GSPC": "S&P 500",
        "^KS200": "KOSPI200",
    }
    return mapping.get(benchmark_ticker, benchmark_ticker)
