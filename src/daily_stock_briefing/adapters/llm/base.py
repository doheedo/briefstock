from abc import ABC, abstractmethod

from daily_stock_briefing.domain.models import SymbolBriefing


class LlmClassifier(ABC):
    @abstractmethod
    def refine_briefing(self, briefing: SymbolBriefing) -> SymbolBriefing:
        """Return an enriched symbol briefing without changing provider contracts."""
        pass

    @abstractmethod
    def summarize_report(self, briefings: list[SymbolBriefing], default_summary: str) -> str:
        """Return a 3-line overall summary of the report."""
        pass
