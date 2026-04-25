from enum import StrEnum


class EventCategory(StrEnum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    REGULATION = "regulation"
    LITIGATION = "litigation"
    MNA = "mna"
    PRODUCT = "product"
    CUSTOMER_CONTRACT = "customer_contract"
    MANAGEMENT = "management"
    FINANCING = "financing"
    INSIDER_TRANSACTION = "insider_transaction"
    MACRO_EXPOSURE = "macro_exposure"
    NOISE = "noise"


class ThesisImpact(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class DailyPriority(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SourcePriority(StrEnum):
    FILINGS = "filings"
    NEWS = "news"
    PRICE = "price"
