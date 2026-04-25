# Daily Stock Briefing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal Python repository that generates a daily stock briefing from a watchlist, writes HTML and JSON reports, and sends a Telegram HTML summary with optional HTML attachment, while staying runnable on an Oracle-hosted Linux server.

**Architecture:** Use a port-and-adapter batch application. Keep domain models and rule-based scoring in `services`, isolate provider-specific HTTP work in `adapters`, and keep rendering/publishing separate from collection so provider changes do not force pipeline rewrites. Runtime code should remain Linux-friendly for Oracle server deployment, while local development commands can stay Windows-specific.

**Tech Stack:** Python 3.12, `pydantic`, `PyYAML`, `httpx`, `jinja2`, `yfinance`, `python-dotenv`, `pytest`

---

## File Map

- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `config/watchlist.yaml`
- Create: `config/providers.yaml`
- Create: `src/daily_stock_briefing/__init__.py`
- Create: `src/daily_stock_briefing/domain/models.py`
- Create: `src/daily_stock_briefing/domain/enums.py`
- Create: `src/daily_stock_briefing/services/config_loader.py`
- Create: `src/daily_stock_briefing/services/news_dedupe.py`
- Create: `src/daily_stock_briefing/services/event_classifier.py`
- Create: `src/daily_stock_briefing/services/report_builder.py`
- Create: `src/daily_stock_briefing/adapters/prices/base.py`
- Create: `src/daily_stock_briefing/adapters/prices/yfinance_adapter.py`
- Create: `src/daily_stock_briefing/adapters/news/base.py`
- Create: `src/daily_stock_briefing/adapters/news/http_news_adapter.py`
- Create: `src/daily_stock_briefing/adapters/filings/base.py`
- Create: `src/daily_stock_briefing/adapters/filings/sec_adapter.py`
- Create: `src/daily_stock_briefing/adapters/filings/dart_adapter.py`
- Create: `src/daily_stock_briefing/adapters/llm/base.py`
- Create: `src/daily_stock_briefing/adapters/telegram/client.py`
- Create: `src/daily_stock_briefing/renderers/telegram_html.py`
- Create: `src/daily_stock_briefing/renderers/html_report.py`
- Create: `src/daily_stock_briefing/jobs/run_daily_briefing.py`
- Create: `scripts/send_telegram_test.py`
- Create: `reports/html/sample-2026-04-24.html`
- Create: `reports/json/.gitkeep`
- Create: `.github/workflows/daily-briefing.yml`
- Create: `deploy/oracle/run_daily_briefing.sh`
- Create: `deploy/oracle/daily-stock-briefing.service`
- Create: `deploy/oracle/daily-stock-briefing.timer`
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `skills/daily-stock-briefing/SKILL.md`
- Create: `tests/conftest.py`
- Create: `tests/test_config_loader.py`
- Create: `tests/test_news_dedupe.py`
- Create: `tests/test_event_classifier.py`
- Create: `tests/test_telegram_renderer.py`
- Create: `tests/test_run_daily_briefing.py`
- Create: `tests/fixtures/sample_watchlist.yaml`
- Create: `tests/fixtures/sample_news.json`
- Create: `tests/fixtures/sample_filings.json`

## Task 1: Bootstrap the Repository and Tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/daily_stock_briefing/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing packaging smoke test**

```python
# tests/conftest.py
from pathlib import Path


def test_package_root_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "src" / "daily_stock_briefing").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/conftest.py -v`
Expected: `FAIL` with `AssertionError` because `src/daily_stock_briefing` does not exist yet.

- [ ] **Step 3: Write minimal packaging and dependency metadata**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "daily-stock-briefing"
version = "0.1.0"
description = "Daily delta briefing for a fixed stock watchlist"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "httpx>=0.27",
  "jinja2>=3.1",
  "pydantic>=2.7",
  "PyYAML>=6.0",
  "python-dotenv>=1.0",
  "yfinance>=0.2.40",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```gitignore
# .gitignore
.venv/
__pycache__/
.pytest_cache/
*.pyc
.env
reports/json/*.json
```

```env
# .env.example
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
NEWS_API_BASE_URL=
NEWS_API_KEY=
SEC_USER_AGENT=DailyStockBriefing/0.1 contact@example.com
DART_API_KEY=
```

```python
# src/daily_stock_briefing/__init__.py
__all__ = ["__version__"]
__version__ = "0.1.0"
```

- [ ] **Step 4: Create and use the project-local virtual environment**

Run: `py -m venv .venv`
Expected: `.venv` directory created.

Run: `.\.venv\Scripts\python.exe -m pip install -e .[dev]`
Expected: editable install succeeds and `daily-stock-briefing` is installed in the local venv.

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/conftest.py -v`
Expected: `1 passed`

- [ ] **Step 6: Check git status without committing**

Run: `git status --short`
Expected: new files listed. Do not create a commit unless the user explicitly asks.

## Task 2: Define Domain Models and Watchlist Loading

**Files:**
- Create: `src/daily_stock_briefing/domain/enums.py`
- Create: `src/daily_stock_briefing/domain/models.py`
- Create: `src/daily_stock_briefing/services/config_loader.py`
- Create: `config/watchlist.yaml`
- Create: `tests/fixtures/sample_watchlist.yaml`
- Create: `tests/test_config_loader.py`

- [ ] **Step 1: Write the failing watchlist loader test**

```python
# tests/test_config_loader.py
from pathlib import Path

from daily_stock_briefing.services.config_loader import load_watchlist


def test_load_watchlist_reads_required_fields() -> None:
    items = load_watchlist(Path("tests/fixtures/sample_watchlist.yaml"))
    assert items[0].ticker == "012700.KQ"
    assert items[0].market == "KR"
    assert items[0].keywords == ["리드코프", "엘씨대부", "배당"]
    assert items[0].source_priority == ["filings", "news", "price"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config_loader.py -v`
Expected: `FAIL` with `ModuleNotFoundError` for `daily_stock_briefing.services.config_loader`.

- [ ] **Step 3: Define enums, models, and loader**

```python
# src/daily_stock_briefing/domain/enums.py
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
```

```python
# src/daily_stock_briefing/domain/models.py
from datetime import datetime

from pydantic import BaseModel, Field

from daily_stock_briefing.domain.enums import DailyPriority, EventCategory, ThesisImpact


class WatchlistItem(BaseModel):
    ticker: str
    name: str
    market: str
    thesis: str
    keywords: list[str] = Field(default_factory=list)
    source_priority: list[str] = Field(default_factory=lambda: ["filings", "news", "price"])


class PriceSnapshot(BaseModel):
    ticker: str
    previous_close: float
    close: float
    change: float
    change_pct: float
    currency: str
    as_of: datetime
    source: str


class NewsItem(BaseModel):
    id: str
    ticker: str
    title: str
    summary: str
    publisher: str
    url: str
    canonical_url: str
    published_at: datetime
    source: str
    matched_keywords: list[str] = Field(default_factory=list)


class FilingItem(BaseModel):
    id: str
    ticker: str
    filing_type: str
    title: str
    filed_at: datetime
    event_date: datetime | None = None
    filing_url: str
    source_system: str
    raw_excerpt: str = ""


class CompanyEvent(BaseModel):
    ticker: str
    category: EventCategory
    importance_score: int
    thesis_impact: ThesisImpact
    summary: str
    evidence: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class SymbolBriefing(BaseModel):
    watchlist_item: WatchlistItem
    price_snapshot: PriceSnapshot | None = None
    major_news: list[NewsItem] = Field(default_factory=list)
    filings: list[FilingItem] = Field(default_factory=list)
    derived_events: list[CompanyEvent] = Field(default_factory=list)
    thesis_summary: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    priority: DailyPriority = DailyPriority.LOW


class DailyBriefingReport(BaseModel):
    run_date: str
    market_summary: str
    symbol_briefings: list[SymbolBriefing]
    delivery_metadata: dict[str, str] = Field(default_factory=dict)
```

```python
# src/daily_stock_briefing/services/config_loader.py
from pathlib import Path

import yaml

from daily_stock_briefing.domain.models import WatchlistItem


def load_watchlist(path: Path) -> list[WatchlistItem]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [WatchlistItem.model_validate(item) for item in payload["watchlist"]]
```

```yaml
# tests/fixtures/sample_watchlist.yaml
watchlist:
  - ticker: 012700.KQ
    name: 리드코프
    market: KR
    thesis: 디케이마린과 엘씨대부 현금흐름, 배당여력 점검
    keywords: [리드코프, 엘씨대부, 배당]
    source_priority: [filings, news, price]
```

```yaml
# config/watchlist.yaml
watchlist:
  - ticker: 012700.KQ
    name: 리드코프
    market: KR
    thesis: 디케이마린과 엘씨대부 현금흐름, 배당여력 점검
    keywords: [리드코프, 엘씨대부, 배당]
    source_priority: [filings, news, price]
  - ticker: 033310.KQ
    name: 엠투엔
    market: KR
    thesis: 리드코프 지배구조 및 지분 관련 변수 추적
    keywords: [엠투엔, 리드코프, 지배구조]
    source_priority: [filings, news, price]
```

- [ ] **Step 4: Run the watchlist test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config_loader.py -v`
Expected: `1 passed`

- [ ] **Step 5: Check git status without committing**

Run: `git status --short`
Expected: domain, config, and test files listed.

## Task 3: Add Price Adapter and News Deduplication

**Files:**
- Create: `src/daily_stock_briefing/adapters/prices/base.py`
- Create: `src/daily_stock_briefing/adapters/prices/yfinance_adapter.py`
- Create: `src/daily_stock_briefing/adapters/news/base.py`
- Create: `src/daily_stock_briefing/adapters/news/http_news_adapter.py`
- Create: `src/daily_stock_briefing/services/news_dedupe.py`
- Create: `tests/fixtures/sample_news.json`
- Create: `tests/test_news_dedupe.py`

- [ ] **Step 1: Write the failing news dedupe test**

```python
# tests/test_news_dedupe.py
from datetime import datetime, timedelta

from daily_stock_briefing.domain.models import NewsItem
from daily_stock_briefing.services.news_dedupe import dedupe_news


def test_dedupe_news_collapses_same_story() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="A",
            publisher="SourceA",
            url="https://example.com/a?utm=1",
            canonical_url="https://example.com/a",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="LC",
            title="LendingClub raises guidance ",
            summary="B",
            publisher="SourceB",
            url="https://example.com/a",
            canonical_url="https://example.com/a",
            published_at=now + timedelta(minutes=5),
            source="api",
        ),
    ]
    deduped = dedupe_news(items)
    assert len(deduped) == 1
    assert deduped[0].publisher == "SourceA"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_news_dedupe.py -v`
Expected: `FAIL` with `ModuleNotFoundError` for `news_dedupe`.

- [ ] **Step 3: Add the price port, reference adapter, news port, and deduper**

```python
# src/daily_stock_briefing/adapters/prices/base.py
from abc import ABC, abstractmethod

from daily_stock_briefing.domain.models import PriceSnapshot


class PriceProvider(ABC):
    @abstractmethod
    def fetch_daily_snapshot(self, ticker: str) -> PriceSnapshot | None: ...
```

```python
# src/daily_stock_briefing/adapters/prices/yfinance_adapter.py
from datetime import datetime, timezone

import yfinance as yf

from daily_stock_briefing.adapters.prices.base import PriceProvider
from daily_stock_briefing.domain.models import PriceSnapshot


class YFinancePriceProvider(PriceProvider):
    def fetch_daily_snapshot(self, ticker: str) -> PriceSnapshot | None:
        history = yf.Ticker(ticker).history(period="2d", interval="1d")
        if len(history) < 2:
            return None
        previous_close = float(history["Close"].iloc[-2])
        close = float(history["Close"].iloc[-1])
        return PriceSnapshot(
            ticker=ticker,
            previous_close=previous_close,
            close=close,
            change=close - previous_close,
            change_pct=((close - previous_close) / previous_close) * 100,
            currency="USD",
            as_of=datetime.now(timezone.utc),
            source="yfinance",
        )
```

```python
# src/daily_stock_briefing/adapters/news/base.py
from abc import ABC, abstractmethod

from daily_stock_briefing.domain.models import NewsItem, WatchlistItem


class NewsProvider(ABC):
    @abstractmethod
    def fetch_news(self, item: WatchlistItem) -> list[NewsItem]: ...
```

```python
# src/daily_stock_briefing/adapters/news/http_news_adapter.py
from datetime import datetime

import httpx

from daily_stock_briefing.adapters.news.base import NewsProvider
from daily_stock_briefing.domain.models import NewsItem, WatchlistItem


class HttpNewsProvider(NewsProvider):
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def fetch_news(self, item: WatchlistItem) -> list[NewsItem]:
        params = {"q": " OR ".join([item.name, *item.keywords]), "apiKey": self._api_key}
        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(self._base_url, params=params)
            response.raise_for_status()
        payload = response.json()
        articles: list[NewsItem] = []
        for raw in payload.get("articles", []):
            articles.append(
                NewsItem(
                    id=raw.get("url", raw["title"]),
                    ticker=item.ticker,
                    title=raw["title"],
                    summary=raw.get("description", ""),
                    publisher=raw.get("source", {}).get("name", "unknown"),
                    url=raw["url"],
                    canonical_url=raw["url"].split("?")[0],
                    published_at=datetime.fromisoformat(raw["publishedAt"].replace("Z", "+00:00")),
                    source="http_news",
                    matched_keywords=item.keywords,
                )
            )
        return articles
```

```python
# src/daily_stock_briefing/services/news_dedupe.py
from collections.abc import Iterable

from daily_stock_briefing.domain.models import NewsItem


def _normalize_title(value: str) -> str:
    return " ".join(value.strip().lower().split())


def dedupe_news(items: Iterable[NewsItem]) -> list[NewsItem]:
    selected: dict[tuple[str, str], NewsItem] = {}
    for item in items:
        key = (item.canonical_url, _normalize_title(item.title))
        if key not in selected:
            selected[key] = item
    return sorted(selected.values(), key=lambda item: item.published_at, reverse=True)
```

- [ ] **Step 4: Run the news dedupe test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_news_dedupe.py -v`
Expected: `1 passed`

- [ ] **Step 5: Add one live-smoke command for the price adapter**

Run: `.\.venv\Scripts\python.exe -c "from daily_stock_briefing.adapters.prices.yfinance_adapter import YFinancePriceProvider; print(YFinancePriceProvider().fetch_daily_snapshot('SNOW'))"`
Expected: a `PriceSnapshot(...)` string or `None`, but no import error.

- [ ] **Step 6: Check git status without committing**

Run: `git status --short`
Expected: adapter and service files listed.

## Task 4: Add SEC and DART Filing Adapters

**Files:**
- Create: `src/daily_stock_briefing/adapters/filings/base.py`
- Create: `src/daily_stock_briefing/adapters/filings/sec_adapter.py`
- Create: `src/daily_stock_briefing/adapters/filings/dart_adapter.py`
- Create: `tests/fixtures/sample_filings.json`
- Modify: `tests/conftest.py`
- Modify: `tests/test_run_daily_briefing.py`

- [ ] **Step 1: Write the failing filing normalization test**

```python
# tests/test_run_daily_briefing.py
from datetime import datetime, timezone

from daily_stock_briefing.adapters.filings.sec_adapter import normalize_sec_filing


def test_normalize_sec_filing_maps_common_fields() -> None:
    raw = {
        "accessionNumber": "0000001",
        "form": "8-K",
        "filingDate": "2026-04-24",
        "primaryDocDescription": "Current report",
        "primaryDocument": "doc.htm",
    }
    item = normalize_sec_filing("LC", raw)
    assert item.ticker == "LC"
    assert item.filing_type == "8-K"
    assert item.source_system == "SEC"
    assert item.filed_at == datetime(2026, 4, 24, tzinfo=timezone.utc)
```

- [ ] **Step 2: Run the filing test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_run_daily_briefing.py::test_normalize_sec_filing_maps_common_fields -v`
Expected: `FAIL` with `ModuleNotFoundError` for `sec_adapter`.

- [ ] **Step 3: Add filing ports and region adapters**

```python
# src/daily_stock_briefing/adapters/filings/base.py
from abc import ABC, abstractmethod

from daily_stock_briefing.domain.models import FilingItem, WatchlistItem


class FilingProvider(ABC):
    @abstractmethod
    def fetch_filings(self, item: WatchlistItem) -> list[FilingItem]: ...
```

```python
# src/daily_stock_briefing/adapters/filings/sec_adapter.py
from datetime import datetime, timezone

import httpx

from daily_stock_briefing.adapters.filings.base import FilingProvider
from daily_stock_briefing.domain.models import FilingItem, WatchlistItem


def normalize_sec_filing(ticker: str, raw: dict) -> FilingItem:
    filed_at = datetime.fromisoformat(raw["filingDate"] + "T00:00:00+00:00")
    accession = raw["accessionNumber"].replace("-", "")
    return FilingItem(
        id=accession,
        ticker=ticker,
        filing_type=raw["form"],
        title=raw.get("primaryDocDescription", raw["form"]),
        filed_at=filed_at,
        filing_url=f"https://www.sec.gov/Archives/edgar/data/{accession}/{raw['primaryDocument']}",
        source_system="SEC",
        raw_excerpt=raw.get("primaryDocDescription", ""),
    )


class SecFilingProvider(FilingProvider):
    def __init__(self, user_agent: str) -> None:
        self._headers = {"User-Agent": user_agent}

    def fetch_filings(self, item: WatchlistItem) -> list[FilingItem]:
        with httpx.Client(headers=self._headers, timeout=10.0) as client:
            response = client.get(f"https://data.sec.gov/submissions/{item.ticker}.json")
            response.raise_for_status()
        recent = response.json().get("filings", {}).get("recent", {})
        rows = zip(
            recent.get("accessionNumber", []),
            recent.get("form", []),
            recent.get("filingDate", []),
            strict=False,
        )
        filings: list[FilingItem] = []
        for accession_number, form, filing_date in rows:
            filings.append(
                normalize_sec_filing(
                    item.ticker,
                    {
                        "accessionNumber": accession_number,
                        "form": form,
                        "filingDate": filing_date,
                        "primaryDocDescription": form,
                        "primaryDocument": "index.htm",
                    },
                )
            )
        return filings[:5]
```

```python
# src/daily_stock_briefing/adapters/filings/dart_adapter.py
from datetime import datetime, timezone

import httpx

from daily_stock_briefing.adapters.filings.base import FilingProvider
from daily_stock_briefing.domain.models import FilingItem, WatchlistItem


class DartFilingProvider(FilingProvider):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def fetch_filings(self, item: WatchlistItem) -> list[FilingItem]:
        params = {"crtfc_key": self._api_key, "corp_code": item.ticker, "page_count": 5}
        with httpx.Client(timeout=10.0) as client:
            response = client.get("https://opendart.fss.or.kr/api/list.json", params=params)
            response.raise_for_status()
        payload = response.json()
        filings: list[FilingItem] = []
        for row in payload.get("list", []):
            filed_at = datetime.fromisoformat(row["rcept_dt"] + "T00:00:00+09:00").astimezone(timezone.utc)
            filings.append(
                FilingItem(
                    id=row["rcept_no"],
                    ticker=item.ticker,
                    filing_type=row["report_nm"],
                    title=row["report_nm"],
                    filed_at=filed_at,
                    filing_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={row['rcept_no']}",
                    source_system="DART",
                    raw_excerpt=row.get("flr_nm", ""),
                )
            )
        return filings
```

- [ ] **Step 4: Run the filing normalization test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_run_daily_briefing.py::test_normalize_sec_filing_maps_common_fields -v`
Expected: `1 passed`

- [ ] **Step 5: Add a DART smoke import check**

Run: `.\.venv\Scripts\python.exe -c "from daily_stock_briefing.adapters.filings.dart_adapter import DartFilingProvider; print(DartFilingProvider)"`
Expected: prints the class representation without import errors.

- [ ] **Step 6: Check git status without committing**

Run: `git status --short`
Expected: filing adapters and test updates listed.

## Task 5: Add Event Classification, Thesis Impact, and Priority Rules

**Files:**
- Create: `src/daily_stock_briefing/services/event_classifier.py`
- Create: `src/daily_stock_briefing/services/report_builder.py`
- Create: `tests/test_event_classifier.py`

- [ ] **Step 1: Write the failing classification test**

```python
# tests/test_event_classifier.py
from datetime import datetime, timezone

from daily_stock_briefing.domain.enums import DailyPriority, EventCategory, ThesisImpact
from daily_stock_briefing.domain.models import FilingItem, NewsItem, PriceSnapshot, WatchlistItem
from daily_stock_briefing.services.report_builder import build_symbol_briefing


def test_negative_guidance_becomes_high_priority() -> None:
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="US",
        thesis="credit quality and deposit funding",
        keywords=["LendingClub", "guidance"],
        source_priority=["filings", "news", "price"],
    )
    price = PriceSnapshot(
        ticker="LC",
        previous_close=10.0,
        close=8.5,
        change=-1.5,
        change_pct=-15.0,
        currency="USD",
        as_of=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source="yfinance",
    )
    news = [
        NewsItem(
            id="n1",
            ticker="LC",
            title="LendingClub cuts full-year guidance",
            summary="Guidance reduced after weaker originations.",
            publisher="Reuters",
            url="https://example.com/guidance",
            canonical_url="https://example.com/guidance",
            published_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
            source="http_news",
            matched_keywords=["guidance"],
        )
    ]
    briefing = build_symbol_briefing(item, price, news, [])
    assert briefing.derived_events[0].category == EventCategory.GUIDANCE
    assert briefing.derived_events[0].thesis_impact == ThesisImpact.NEGATIVE
    assert briefing.priority == DailyPriority.HIGH
```

- [ ] **Step 2: Run the classification test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_event_classifier.py -v`
Expected: `FAIL` with `ModuleNotFoundError` for `report_builder`.

- [ ] **Step 3: Implement rule-based event and report building**

```python
# src/daily_stock_briefing/services/event_classifier.py
from daily_stock_briefing.domain.enums import EventCategory, ThesisImpact
from daily_stock_briefing.domain.models import CompanyEvent, FilingItem, NewsItem, WatchlistItem


def classify_news_event(item: WatchlistItem, news: NewsItem) -> CompanyEvent:
    title = news.title.lower()
    if "guidance" in title or "outlook" in title:
        category = EventCategory.GUIDANCE
        impact = ThesisImpact.NEGATIVE if any(word in title for word in ["cut", "lower", "miss"]) else ThesisImpact.UNKNOWN
        score = 5 if impact == ThesisImpact.NEGATIVE else 4
    elif "earnings" in title or "results" in title:
        category = EventCategory.EARNINGS
        impact = ThesisImpact.UNKNOWN
        score = 5
    elif "acquire" in title or "merger" in title:
        category = EventCategory.MNA
        impact = ThesisImpact.UNKNOWN
        score = 4
    else:
        category = EventCategory.NOISE
        impact = ThesisImpact.NEUTRAL
        score = 2
    return CompanyEvent(
        ticker=item.ticker,
        category=category,
        importance_score=score,
        thesis_impact=impact,
        summary=news.summary or news.title,
        evidence=[news.title],
        source_refs=[news.url],
    )


def classify_filing_event(item: WatchlistItem, filing: FilingItem) -> CompanyEvent:
    title = filing.title.lower()
    category = EventCategory.FINANCING if "convertible" in title or "offering" in title else EventCategory.NOISE
    impact = ThesisImpact.UNKNOWN if category != EventCategory.NOISE else ThesisImpact.NEUTRAL
    score = 4 if category != EventCategory.NOISE else 2
    return CompanyEvent(
        ticker=item.ticker,
        category=category,
        importance_score=score,
        thesis_impact=impact,
        summary=filing.title,
        evidence=[filing.raw_excerpt or filing.title],
        source_refs=[filing.filing_url],
    )
```

```python
# src/daily_stock_briefing/services/report_builder.py
from daily_stock_briefing.domain.enums import DailyPriority, ThesisImpact
from daily_stock_briefing.domain.models import FilingItem, NewsItem, PriceSnapshot, SymbolBriefing, WatchlistItem
from daily_stock_briefing.services.event_classifier import classify_filing_event, classify_news_event


def build_symbol_briefing(
    item: WatchlistItem,
    price_snapshot: PriceSnapshot | None,
    news_items: list[NewsItem],
    filing_items: list[FilingItem],
) -> SymbolBriefing:
    events = [classify_news_event(item, news) for news in news_items[:3]]
    events.extend(classify_filing_event(item, filing) for filing in filing_items[:3])
    if any(event.thesis_impact == ThesisImpact.NEGATIVE for event in events) or any(event.importance_score >= 4 for event in events):
        priority = DailyPriority.HIGH
    elif any(event.importance_score == 3 for event in events):
        priority = DailyPriority.MEDIUM
    else:
        priority = DailyPriority.LOW
    thesis_summary = "No thesis-relevant update."
    if events:
        thesis_summary = f"{events[0].thesis_impact.value}: {events[0].summary}"
    return SymbolBriefing(
        watchlist_item=item,
        price_snapshot=price_snapshot,
        major_news=news_items[:3],
        filings=filing_items[:3],
        derived_events=events,
        thesis_summary=thesis_summary,
        follow_up_questions=["Does this change the core thesis today?"] if events else [],
        priority=priority,
    )
```

- [ ] **Step 4: Run the classification test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_event_classifier.py -v`
Expected: `1 passed`

- [ ] **Step 5: Run the narrow regression set**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config_loader.py tests/test_news_dedupe.py tests/test_event_classifier.py -v`
Expected: all listed tests pass.

- [ ] **Step 6: Check git status without committing**

Run: `git status --short`
Expected: classifier and builder files listed.

## Task 6: Add Telegram-Safe Rendering and HTML Report Output

**Files:**
- Create: `src/daily_stock_briefing/renderers/telegram_html.py`
- Create: `src/daily_stock_briefing/renderers/html_report.py`
- Create: `src/daily_stock_briefing/adapters/telegram/client.py`
- Create: `tests/test_telegram_renderer.py`
- Create: `reports/html/sample-2026-04-24.html`

- [ ] **Step 1: Write the failing Telegram HTML renderer test**

```python
# tests/test_telegram_renderer.py
from daily_stock_briefing.domain.enums import DailyPriority
from daily_stock_briefing.domain.models import SymbolBriefing, WatchlistItem
from daily_stock_briefing.renderers.telegram_html import render_symbol_line


def test_render_symbol_line_uses_only_supported_tags() -> None:
    briefing = SymbolBriefing(
        watchlist_item=WatchlistItem(
            ticker="SNOW",
            name="Snowflake",
            market="US",
            thesis="data platform moat",
            keywords=["Snowflake"],
            source_priority=["news", "filings", "price"],
        ),
        thesis_summary="negative: growth slowdown",
        follow_up_questions=["Does usage reaccelerate next quarter?"],
        priority=DailyPriority.HIGH,
    )
    html = render_symbol_line(briefing)
    assert "<b>SNOW</b>" in html
    assert "<ul>" not in html
    assert "<table>" not in html
```

- [ ] **Step 2: Run the renderer test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_telegram_renderer.py -v`
Expected: `FAIL` with `ModuleNotFoundError` for `telegram_html`.

- [ ] **Step 3: Implement Telegram renderer, HTML renderer, and Telegram client**

```python
# src/daily_stock_briefing/renderers/telegram_html.py
from html import escape

from daily_stock_briefing.domain.models import DailyBriefingReport, SymbolBriefing


def render_symbol_line(briefing: SymbolBriefing) -> str:
    summary = escape(briefing.thesis_summary)
    questions = " / ".join(escape(question) for question in briefing.follow_up_questions[:2])
    return (
        f"<b>{escape(briefing.watchlist_item.ticker)}</b> "
        f"({escape(briefing.priority.value)})\n"
        f"• {summary}\n"
        f"• Check: {questions}"
    )


def render_telegram_html(report: DailyBriefingReport) -> str:
    parts = [f"<b>Daily Briefing {escape(report.run_date)}</b>", escape(report.market_summary)]
    parts.extend(render_symbol_line(briefing) for briefing in report.symbol_briefings)
    return "\n\n".join(parts)
```

```python
# src/daily_stock_briefing/renderers/html_report.py
from pathlib import Path

from jinja2 import Template

from daily_stock_briefing.domain.models import DailyBriefingReport


PAGE = Template(
    """
    <!doctype html>
    <html lang="ko">
    <head><meta charset="utf-8"><title>{{ report.run_date }}</title></head>
    <body>
      <h1>Daily Stock Briefing - {{ report.run_date }}</h1>
      <p>{{ report.market_summary }}</p>
      {% for briefing in report.symbol_briefings %}
      <section>
        <h2>{{ briefing.watchlist_item.ticker }} - {{ briefing.watchlist_item.name }}</h2>
        <p><strong>Priority:</strong> {{ briefing.priority.value }}</p>
        <p><strong>Thesis Impact:</strong> {{ briefing.thesis_summary }}</p>
      </section>
      {% endfor %}
    </body>
    </html>
    """
)


def write_html_report(report: DailyBriefingReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE.render(report=report), encoding="utf-8")
    return path
```

```python
# src/daily_stock_briefing/adapters/telegram/client.py
from pathlib import Path

import httpx


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._chat_id = chat_id

    def send_html(self, text: str) -> dict:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{self._base_url}/sendMessage",
                json={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            )
            response.raise_for_status()
            return response.json()

    def send_document(self, path: Path, caption: str) -> dict:
        with httpx.Client(timeout=30.0) as client:
            with path.open("rb") as handle:
                response = client.post(
                    f"{self._base_url}/sendDocument",
                    data={"chat_id": self._chat_id, "caption": caption},
                    files={"document": (path.name, handle, "text/html")},
                )
            response.raise_for_status()
            return response.json()
```

- [ ] **Step 4: Run the Telegram renderer test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_telegram_renderer.py -v`
Expected: `1 passed`

- [ ] **Step 5: Save one sample HTML artifact**

Run: `.\.venv\Scripts\python.exe -c "from pathlib import Path; Path('reports/html/sample-2026-04-24.html').write_text('<html><body>sample</body></html>', encoding='utf-8')"`
Expected: sample report file created.

- [ ] **Step 6: Check git status without committing**

Run: `git status --short`
Expected: renderer, client, test, and sample report files listed.

## Task 7: Wire the Daily Job, Sample Inputs, Workflow, and Docs

**Files:**
- Create: `src/daily_stock_briefing/jobs/run_daily_briefing.py`
- Create: `scripts/send_telegram_test.py`
- Create: `config/providers.yaml`
- Create: `.github/workflows/daily-briefing.yml`
- Create: `deploy/oracle/run_daily_briefing.sh`
- Create: `deploy/oracle/daily-stock-briefing.service`
- Create: `deploy/oracle/daily-stock-briefing.timer`
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `skills/daily-stock-briefing/SKILL.md`
- Modify: `tests/test_run_daily_briefing.py`

- [ ] **Step 1: Write the failing orchestration smoke test**

```python
# tests/test_run_daily_briefing.py
from pathlib import Path

from daily_stock_briefing.jobs.run_daily_briefing import main


def test_main_writes_html_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path("config").mkdir()
    Path("config/watchlist.yaml").write_text(
        "watchlist:\\n  - ticker: LC\\n    name: LendingClub\\n    market: US\\n    thesis: funding\\n    keywords: [LendingClub]\\n    source_priority: [news, filings, price]\\n",
        encoding="utf-8",
    )
    exit_code = main(["--date", "2026-04-24", "--skip-telegram"])
    assert exit_code == 0
    assert Path("reports/html/2026-04-24.html").exists()
```

- [ ] **Step 2: Run the orchestration test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_run_daily_briefing.py::test_main_writes_html_report -v`
Expected: `FAIL` with `ModuleNotFoundError` for `run_daily_briefing`.

- [ ] **Step 3: Implement the daily job and Telegram test script**

```python
# src/daily_stock_briefing/jobs/run_daily_briefing.py
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from daily_stock_briefing.adapters.prices.yfinance_adapter import YFinancePriceProvider
from daily_stock_briefing.domain.models import DailyBriefingReport
from daily_stock_briefing.renderers.html_report import write_html_report
from daily_stock_briefing.renderers.telegram_html import render_telegram_html
from daily_stock_briefing.services.config_loader import load_watchlist
from daily_stock_briefing.services.report_builder import build_symbol_briefing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--skip-telegram", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv()
    watchlist = load_watchlist(Path("config/watchlist.yaml"))
    price_provider = YFinancePriceProvider()
    briefings = []
    for item in watchlist:
        price = price_provider.fetch_daily_snapshot(item.ticker)
        briefings.append(build_symbol_briefing(item, price, [], []))

    report = DailyBriefingReport(
        run_date=args.date,
        market_summary="Minimal market summary for MVP.",
        symbol_briefings=briefings,
        delivery_metadata={},
    )
    html_path = write_html_report(report, Path("reports/html") / f"{args.date}.html")
    json_path = Path("reports/json") / f"{args.date}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    if not args.skip_telegram and os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        from daily_stock_briefing.adapters.telegram.client import TelegramClient

        client = TelegramClient(os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"])
        client.send_html(render_telegram_html(report))
        client.send_document(html_path, caption=f"Daily report {args.date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```python
# scripts/send_telegram_test.py
import os
from pathlib import Path

from dotenv import load_dotenv

from daily_stock_briefing.adapters.telegram.client import TelegramClient


load_dotenv()
client = TelegramClient(os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"])
client.send_html("<b>Telegram test</b>\n• HTML parse_mode check")
sample = Path("reports/html/sample-2026-04-24.html")
if sample.exists():
    client.send_document(sample, "Sample HTML report")
```

```yaml
# .github/workflows/daily-briefing.yml
name: daily-briefing

on:
  schedule:
    - cron: "0 23 * * *"
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m venv .venv
      - run: ./.venv/bin/python -m pip install -e .[dev]
      - run: ./.venv/bin/python -m daily_stock_briefing.jobs.run_daily_briefing --date "$(date -u +%F)"
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          NEWS_API_BASE_URL: ${{ secrets.NEWS_API_BASE_URL }}
          NEWS_API_KEY: ${{ secrets.NEWS_API_KEY }}
          SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}
          DART_API_KEY: ${{ secrets.DART_API_KEY }}
```

```bash
# deploy/oracle/run_daily_briefing.sh
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/daily-stock-briefing"
cd "$PROJECT_DIR"

source .venv/bin/activate
python -m daily_stock_briefing.jobs.run_daily_briefing --date "$(date +%F)"
```

```ini
# deploy/oracle/daily-stock-briefing.service
[Unit]
Description=Daily Stock Briefing job
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/daily-stock-briefing
EnvironmentFile=/opt/daily-stock-briefing/.env
ExecStart=/opt/daily-stock-briefing/deploy/oracle/run_daily_briefing.sh
```

```ini
# deploy/oracle/daily-stock-briefing.timer
[Unit]
Description=Run Daily Stock Briefing at 08:00 KST

[Timer]
OnCalendar=*-*-* 08:00:00 Asia/Seoul
Persistent=true

[Install]
WantedBy=timers.target
```

```markdown
# README.md
## Setup
1. `py -m venv .venv`
2. `.\.venv\Scripts\python.exe -m pip install -e .[dev]`
3. Copy `.env.example` values into `.env`
4. Edit `config/watchlist.yaml`

## Run
`.\.venv\Scripts\python.exe -m daily_stock_briefing.jobs.run_daily_briefing --date 2026-04-24 --skip-telegram`

## GitHub Secrets
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `NEWS_API_BASE_URL`
- `NEWS_API_KEY`
- `SEC_USER_AGENT`
- `DART_API_KEY`

## Oracle Server Deployment
1. Copy the repo to `/opt/daily-stock-briefing`
2. Create Linux venv: `python3 -m venv .venv`
3. Install: `.venv/bin/python -m pip install -e .`
4. Fill `/opt/daily-stock-briefing/.env`
5. Enable systemd timer:
   - `sudo cp deploy/oracle/daily-stock-briefing.service /etc/systemd/system/`
   - `sudo cp deploy/oracle/daily-stock-briefing.timer /etc/systemd/system/`
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now daily-stock-briefing.timer`
```

```markdown
# AGENTS.md
## Operating principles
- Prefer the smallest safe change that solves the task.
- Inspect before editing.
- Explain the cause of an error before proposing a fix.
- Keep output concise and concrete.

## Daily briefing conventions
- Treat the project as a delta briefing system, not a deep research system.
- Keep Telegram messages HTML-safe and compact.
- Prefer rule-based event scoring before optional LLM enrichment.
```

```markdown
# skills/daily-stock-briefing/SKILL.md
---
name: daily-stock-briefing
description: Repeatable workflow for the daily stock briefing repository
---

1. Read `config/watchlist.yaml`.
2. Preserve the adapter boundaries in `src/daily_stock_briefing/adapters/`.
3. Keep Telegram output within supported HTML tags.
4. Run the narrowest relevant pytest target after each edit.
5. Do not hardcode secrets.
```

- [ ] **Step 4: Run the orchestration smoke test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_run_daily_briefing.py::test_main_writes_html_report -v`
Expected: `1 passed`

- [ ] **Step 5: Run the minimal full regression set**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config_loader.py tests/test_news_dedupe.py tests/test_event_classifier.py tests/test_telegram_renderer.py tests/test_run_daily_briefing.py -v`
Expected: all tests pass.

- [ ] **Step 6: Manual validation**

Run: `.\.venv\Scripts\python.exe -m daily_stock_briefing.jobs.run_daily_briefing --date 2026-04-24 --skip-telegram`
Expected: `reports/html/2026-04-24.html` and `reports/json/2026-04-24.json` created locally.

Run: `.\.venv\Scripts\python.exe scripts/send_telegram_test.py`
Expected: Telegram test message arrives if `.env` contains valid bot token and chat id.

- [ ] **Step 7: Add Oracle Linux deployment verification**

Run on the Oracle server after sync: `bash deploy/oracle/run_daily_briefing.sh`
Expected: the daily job completes with Linux paths and writes the same `reports/html/YYYY-MM-DD.html` and `reports/json/YYYY-MM-DD.json` artifacts.

Run on the Oracle server after installing the unit files: `systemctl list-timers daily-stock-briefing.timer`
Expected: the timer is visible and scheduled for the next 08:00 Asia/Seoul run.

- [ ] **Step 8: Check git status without committing**

Run: `git status --short`
Expected: job, workflow, docs, and skill files listed.

## Self-Review

### Spec coverage

- Watchlist management in `config/watchlist.yaml`: covered in Task 2
- Price adapter pattern: covered in Task 3
- News deduplication: covered in Task 3
- SEC and DART extensible filing adapters: covered in Task 4
- Required event categories, importance, thesis impact, priority: covered in Task 5
- Telegram HTML restrictions and HTML report path: covered in Task 6 and Task 7
- Daily KST 08:00 GitHub Actions run: covered in Task 7
- Oracle-hosted Linux server compatibility: covered in Task 7
- README, `.env.example`, AGENTS, skill: covered in Task 7

No gaps found.

### Placeholder scan

- No `TODO`, `TBD`, `implement later`, or empty steps remain.

### Type consistency

- `WatchlistItem`, `PriceSnapshot`, `NewsItem`, `FilingItem`, `CompanyEvent`, `SymbolBriefing`, `DailyBriefingReport` are defined before use.
- `build_symbol_briefing()` signature matches the tests and the job entrypoint.
- `render_telegram_html()` consumes `DailyBriefingReport`, consistent with the job.

Plan is internally consistent for MVP scope.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-24-daily-stock-briefing.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
