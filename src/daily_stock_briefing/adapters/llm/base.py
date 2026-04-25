from abc import ABC, abstractmethod

from daily_stock_briefing.domain.models import CompanyEvent, WatchlistItem


class LlmClassifier(ABC):
    @abstractmethod
    def refine_event(self, item: WatchlistItem, event: CompanyEvent) -> CompanyEvent:
        """Return an enriched event without changing provider-neutral contracts."""
