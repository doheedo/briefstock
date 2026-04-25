from abc import ABC, abstractmethod

from daily_stock_briefing.domain.models import PriceSnapshot


class PriceProvider(ABC):
    @abstractmethod
    def fetch_daily_snapshot(
        self, ticker: str, benchmark_ticker: str | None = None
    ) -> PriceSnapshot | None:
        raise NotImplementedError
