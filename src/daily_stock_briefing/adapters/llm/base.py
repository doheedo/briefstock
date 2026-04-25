from abc import ABC, abstractmethod

from daily_stock_briefing.domain.models import SymbolBriefing


class LlmClassifier(ABC):
    @abstractmethod
    def refine_briefing(self, briefing: SymbolBriefing) -> SymbolBriefing:
        """Return an enriched symbol briefing without changing provider contracts."""
