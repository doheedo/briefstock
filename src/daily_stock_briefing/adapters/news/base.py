from abc import ABC, abstractmethod

from daily_stock_briefing.domain.models import NewsItem, WatchlistItem


class NewsProvider(ABC):
    @abstractmethod
    def fetch_news(self, item: WatchlistItem) -> list[NewsItem]:
        raise NotImplementedError
