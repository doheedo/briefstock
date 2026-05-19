from datetime import UTC, datetime, timedelta

import pytest

from daily_stock_briefing.adapters.news.http_news_adapter import HttpNewsProvider
from daily_stock_briefing.adapters.prices.yfinance_adapter import YFinancePriceProvider
from daily_stock_briefing.domain.models import NewsItem
from daily_stock_briefing.domain.models import WatchlistItem
from daily_stock_briefing.services.news_dedupe import dedupe_news


def test_dedupe_news_collapses_same_story_with_url_and_title_normalization() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="A",
            publisher="SourceA",
            url="https://WWW.Example.com/a?utm=1",
            canonical_url="https://WWW.Example.com/a?utm=1",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="LC",
            title=" lendingclub raises guidance ",
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
    assert deduped[0].id == "2"


def test_dedupe_news_treats_default_ports_and_trailing_slashes_as_same_url() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="A",
            publisher="SourceA",
            url="https://www.example.com:443/a/",
            canonical_url="https://www.example.com:443/a/",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="B",
            publisher="SourceB",
            url="https://example.com/a",
            canonical_url="https://example.com/a",
            published_at=now + timedelta(minutes=5),
            source="api",
        ),
    ]

    deduped = dedupe_news(items)

    assert [item.id for item in deduped] == ["2"]


def test_dedupe_news_tolerates_malformed_urls_without_raising() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="A",
            publisher="SourceA",
            url="https://example.com/a",
            canonical_url="https://example.com:bad/a",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="LC",
            title="Different story",
            summary="B",
            publisher="SourceB",
            url="http://[bad-url",
            canonical_url="http://[bad-url",
            published_at=now + timedelta(minutes=5),
            source="api",
        ),
    ]

    deduped = dedupe_news(items)

    assert [item.id for item in deduped] == ["2", "1"]


def test_dedupe_news_falls_back_to_raw_url_when_canonical_url_is_malformed() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="A",
            publisher="SourceA",
            url="https://example.com/a",
            canonical_url="https://example.com:bad/a",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="B",
            publisher="SourceB",
            url="https://www.example.com:443/a/",
            canonical_url="https://example.com:stillbad/a",
            published_at=now + timedelta(minutes=5),
            source="api",
        ),
    ]

    deduped = dedupe_news(items)

    assert [item.id for item in deduped] == ["2"]


def test_dedupe_news_falls_back_to_raw_url_for_malformed_canonical_url_even_when_titles_differ() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="A",
            publisher="SourceA",
            url="https://example.com/a",
            canonical_url="https://example.com:bad/a",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="LC",
            title="LC boosts outlook",
            summary="B",
            publisher="SourceB",
            url="https://www.example.com:443/a/",
            canonical_url="https://example.com:stillbad/a",
            published_at=now + timedelta(minutes=5),
            source="api",
        ),
    ]

    deduped = dedupe_news(items)

    assert [item.id for item in deduped] == ["2"]


def test_dedupe_news_collapses_near_duplicate_titles_within_publish_window() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="LC",
            title="LendingClub raises guidance for 2026",
            summary="A",
            publisher="SourceA",
            url="https://example.com/story-a",
            canonical_url="https://example.com/story-a",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="LC",
            title="LendingClub raises guidance for 2026.",
            summary="B",
            publisher="SourceB",
            url="https://another-source.com/story-b",
            canonical_url="https://another-source.com/story-b",
            published_at=now + timedelta(minutes=20),
            source="api",
        ),
        NewsItem(
            id="3",
            ticker="LC",
            title="LendingClub raises guidance for 2026",
            summary="C",
            publisher="SourceC",
            url="https://later-source.com/story-c",
            canonical_url="https://later-source.com/story-c",
            published_at=now + timedelta(hours=2),
            source="api",
        ),
    ]

    deduped = dedupe_news(items)

    assert [item.id for item in deduped] == ["3", "2"]


def test_dedupe_news_keeps_better_ranked_source_in_duplicate_group() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="A",
            publisher="LowRankWire",
            url="https://example.com/a",
            canonical_url="https://example.com/a",
            published_at=now,
            source="wire",
        ),
        NewsItem(
            id="2",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="B",
            publisher="TopDesk",
            url="https://mirror.example.com/a",
            canonical_url="https://mirror.example.com/a",
            published_at=now + timedelta(minutes=2),
            source="press",
        ),
    ]

    deduped = dedupe_news(items, source_ranks={"TopDesk": 100, "LowRankWire": 10})

    assert len(deduped) == 1
    assert deduped[0].publisher == "TopDesk"


def test_dedupe_news_keeps_same_story_for_different_tickers() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="LC",
            title="Market reacts to guidance",
            summary="A",
            publisher="SourceA",
            url="https://example.com/a",
            canonical_url="https://example.com/a",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="SOFI",
            title="Market reacts to guidance",
            summary="B",
            publisher="SourceB",
            url="https://www.example.com/a?utm=1",
            canonical_url="https://www.example.com/a?utm=1",
            published_at=now + timedelta(minutes=5),
            source="api",
        ),
    ]

    deduped = dedupe_news(items)

    assert [item.ticker for item in deduped] == ["SOFI", "LC"]


def test_dedupe_news_handles_transitive_title_window_independent_of_input_order() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="3",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="late",
            publisher="SourceC",
            url="https://source-c.example/story",
            canonical_url="https://source-c.example/story",
            published_at=now + timedelta(minutes=40),
            source="api",
        ),
        NewsItem(
            id="1",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="early",
            publisher="SourceA",
            url="https://source-a.example/story",
            canonical_url="https://source-a.example/story",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="LC",
            title="LendingClub raises guidance",
            summary="middle",
            publisher="SourceB",
            url="https://source-b.example/story",
            canonical_url="https://source-b.example/story",
            published_at=now + timedelta(minutes=20),
            source="api",
        ),
    ]

    deduped = dedupe_news(items, source_ranks={"SourceB": 10})

    assert [item.id for item in deduped] == ["2"]


def test_dedupe_news_keeps_distinct_korean_titles_within_publish_window() -> None:
    now = datetime(2026, 4, 24, 8, 0, 0)
    items = [
        NewsItem(
            id="1",
            ticker="005930",
            title="삼성전자 실적 발표",
            summary="A",
            publisher="SourceA",
            url="https://example.com/a",
            canonical_url="https://example.com/a",
            published_at=now,
            source="api",
        ),
        NewsItem(
            id="2",
            ticker="005930",
            title="삼성전자 신제품 공개",
            summary="B",
            publisher="SourceB",
            url="https://other.example.com/b",
            canonical_url="https://other.example.com/b",
            published_at=now + timedelta(minutes=10),
            source="api",
        ),
    ]

    deduped = dedupe_news(items)

    assert [item.id for item in deduped] == ["2", "1"]


def test_http_news_provider_skips_malformed_published_at_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "articles": [
            {
                "title": "Valid story",
                "description": "guidance update",
                "url": "https://www.example.com/a?utm=1",
                "publishedAt": "2026-04-24T08:00:00Z",
                "source": {"name": "Example News"},
            },
            {
                "title": "Broken story",
                "description": "guidance update",
                "url": "https://example.com/b",
                "publishedAt": "not-a-date",
                "source": {"name": "Example News"},
            },
        ]
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, params: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.http_news_adapter.httpx.Client",
        FakeClient,
    )

    provider = HttpNewsProvider("https://api.example.com/news", "token")
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="NASDAQ",
        thesis="Test thesis",
        keywords=["guidance"],
    )

    news = provider.fetch_news(item)

    assert [article.title for article in news] == ["Valid story"]
    assert news[0].canonical_url == "https://example.com/a"


def test_http_news_provider_skips_non_dict_article_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "articles": [
            "not-a-dict",
            {
                "title": "Valid story",
                "description": "guidance update",
                "url": "https://example.com/a",
                "publishedAt": "2026-04-24T08:00:00Z",
                "source": {"name": "Example News"},
            },
        ]
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, params: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.http_news_adapter.httpx.Client",
        FakeClient,
    )

    provider = HttpNewsProvider("https://api.example.com/news", "token")
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="NASDAQ",
        thesis="Test thesis",
        keywords=["guidance"],
    )

    news = provider.fetch_news(item)

    assert [article.title for article in news] == ["Valid story"]


def test_http_news_provider_returns_empty_list_for_non_dict_top_level_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[str]:
            return ["not-a-dict"]

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, params: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.http_news_adapter.httpx.Client",
        FakeClient,
    )

    provider = HttpNewsProvider("https://api.example.com/news", "token")
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="NASDAQ",
        thesis="Test thesis",
        keywords=["guidance"],
    )

    news = provider.fetch_news(item)

    assert news == []


def test_http_news_provider_skips_malformed_url_rows_while_keeping_valid_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "articles": [
            {
                "title": "Broken URL story",
                "description": "guidance update",
                "url": "https://example.com:bad/a",
                "publishedAt": "2026-04-24T08:00:00Z",
                "source": {"name": "Example News"},
            },
            {
                "title": "Valid story",
                "description": "guidance update",
                "url": "https://example.com:443/a/",
                "publishedAt": "2026-04-24T09:00:00Z",
                "source": {"name": "Example News"},
            },
        ]
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, params: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.http_news_adapter.httpx.Client",
        FakeClient,
    )

    provider = HttpNewsProvider("https://api.example.com/news", "token")
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="NASDAQ",
        thesis="Test thesis",
        keywords=["guidance"],
    )

    news = provider.fetch_news(item)

    assert [article.title for article in news] == ["Valid story"]
    assert news[0].canonical_url == "https://example.com/a"


def test_http_news_provider_skips_rows_with_malformed_field_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "articles": [
            {
                "title": ["bad-title"],
                "description": {"bad": "description"},
                "content": ["bad-content"],
                "url": "https://example.com/bad",
                "publishedAt": "2026-04-24T08:00:00Z",
                "source": {"name": "Example News"},
            },
            {
                "title": "Valid story",
                "description": "guidance update",
                "content": "guidance details",
                "url": "https://example.com/good",
                "publishedAt": "2026-04-24T09:00:00Z",
                "source": {"name": "Example News"},
            },
        ]
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, params: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.http_news_adapter.httpx.Client",
        FakeClient,
    )

    provider = HttpNewsProvider("https://api.example.com/news", "token")
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="NASDAQ",
        thesis="Test thesis",
        keywords=["guidance"],
    )

    news = provider.fetch_news(item)

    assert [article.title for article in news] == ["Valid story"]


def test_http_news_provider_skips_rows_with_truthy_non_dict_source_while_keeping_valid_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "articles": [
            {
                "title": "Bad source story",
                "description": "guidance update",
                "url": "https://example.com/bad-source",
                "publishedAt": "2026-04-24T08:00:00Z",
                "source": ["not-a-dict"],
            },
            {
                "title": "Valid story",
                "description": "guidance update",
                "url": "https://example.com/good-source",
                "publishedAt": "2026-04-24T09:00:00Z",
                "source": {"name": "Example News"},
            },
        ]
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, params: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.http_news_adapter.httpx.Client",
        FakeClient,
    )

    provider = HttpNewsProvider("https://api.example.com/news", "token")
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="NASDAQ",
        thesis="Test thesis",
        keywords=["guidance"],
    )

    news = provider.fetch_news(item)

    assert [article.title for article in news] == ["Valid story"]


def test_http_news_provider_skips_malformed_or_naive_published_at_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "articles": [
            {
                "title": "Aware story",
                "description": "guidance update",
                "url": "https://example.com/aware",
                "publishedAt": "2026-04-24T08:00:00+09:00",
                "source": {"name": "Example News"},
            },
            {
                "title": "Naive story",
                "description": "guidance update",
                "url": "https://example.com/naive",
                "publishedAt": "2026-04-24T08:00:00",
                "source": {"name": "Example News"},
            },
            {
                "title": "Broken story",
                "description": "guidance update",
                "url": "https://example.com/broken",
                "publishedAt": "not-a-date",
                "source": {"name": "Example News"},
            },
        ]
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, params: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.http_news_adapter.httpx.Client",
        FakeClient,
    )

    provider = HttpNewsProvider("https://api.example.com/news", "token")
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="NASDAQ",
        thesis="Test thesis",
        keywords=["guidance"],
    )

    news = provider.fetch_news(item)

    assert [article.title for article in news] == ["Aware story"]
    assert news[0].published_at.tzinfo is UTC
    assert news[0].published_at.hour == 23


@pytest.mark.parametrize("mode", ["request", "json"])
def test_http_news_provider_returns_empty_list_on_upstream_failures(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            raise ValueError("bad payload")

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, params: dict) -> FakeResponse:
            if mode == "request":
                raise RuntimeError("network down")
            return FakeResponse()

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.http_news_adapter.httpx.Client",
        FakeClient,
    )

    provider = HttpNewsProvider("https://api.example.com/news", "token")
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="NASDAQ",
        thesis="Test thesis",
        keywords=["guidance"],
    )

    news = provider.fetch_news(item)

    assert news == []


def test_http_news_provider_fetches_press_release_query_every_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "articles": [
            {
                "title": "LendingClub press release",
                "description": "guidance update",
                "url": "https://example.com/pr",
                "publishedAt": "2026-04-24T08:00:00Z",
                "source": {"name": "Example News"},
            }
        ]
    }
    calls: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, params: dict) -> FakeResponse:
            calls.append(params)
            return FakeResponse()

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.news.http_news_adapter.httpx.Client",
        FakeClient,
    )

    provider = HttpNewsProvider("https://api.example.com/news", "token")
    item = WatchlistItem(
        ticker="LC",
        name="LendingClub",
        market="NASDAQ",
        thesis="Test thesis",
        keywords=["guidance"],
    )

    news = provider.fetch_news(item)

    assert len(calls) == 2
    assert any("press release" in str(call.get("q", "")).lower() for call in calls)
    assert len(news) == 1
    assert news[0].title == "LendingClub press release"


def test_yfinance_price_provider_uses_metadata_currency(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSeries:
        def __init__(self, values: list[float]) -> None:
            self.iloc = values

        def __len__(self) -> int:
            return len(self.iloc)

    class FakeHistory:
        def __init__(self, closes: list[float]) -> None:
            self._closes = FakeSeries(closes)

        def get(self, key: str) -> FakeSeries | None:
            if key == "Close":
                return self._closes
            return None

    class FakeTicker:
        info = {"currency": "KRW"}

        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, period: str, interval: str) -> FakeHistory:
            return FakeHistory([100.0, 110.0])

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        FakeTicker,
    )

    snapshot = YFinancePriceProvider().fetch_daily_snapshot("LC")

    assert snapshot is not None
    assert snapshot.currency == "KRW"


def test_yfinance_price_provider_returns_none_for_nan_close_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSeries:
        def __init__(self, values: list[float]) -> None:
            self.iloc = values

        def __len__(self) -> int:
            return len(self.iloc)

    class FakeHistory:
        def __init__(self, closes: list[float]) -> None:
            self._closes = FakeSeries(closes)

        def get(self, key: str) -> FakeSeries | None:
            if key == "Close":
                return self._closes
            return None

    class FakeTicker:
        info = {"currency": "USD"}

        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, period: str, interval: str) -> FakeHistory:
            return FakeHistory([100.0, float("nan")])

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        FakeTicker,
    )

    snapshot = YFinancePriceProvider().fetch_daily_snapshot("LC")

    assert snapshot is None


def test_yfinance_price_provider_returns_none_for_null_close_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSeries:
        def __init__(self, values: list[object]) -> None:
            self.iloc = values

        def __len__(self) -> int:
            return len(self.iloc)

    class FakeHistory:
        def __init__(self, closes: list[object]) -> None:
            self._closes = FakeSeries(closes)

        def get(self, key: str) -> FakeSeries | None:
            if key == "Close":
                return self._closes
            return None

    class FakeTicker:
        info = {"currency": "USD"}

        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, period: str, interval: str) -> FakeHistory:
            return FakeHistory([100.0, None])

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        FakeTicker,
    )

    snapshot = YFinancePriceProvider().fetch_daily_snapshot("LC")

    assert snapshot is None


def test_yfinance_price_provider_returns_none_when_provider_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTicker:
        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, period: str, interval: str) -> object:
            raise RuntimeError("provider failure")

        @property
        def info(self) -> dict:
            raise RuntimeError("metadata failure")

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        FakeTicker,
    )

    snapshot = YFinancePriceProvider().fetch_daily_snapshot("LC")

    assert snapshot is None


def test_yfinance_price_provider_uses_fallback_currency_when_metadata_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSeries:
        def __init__(self, values: list[float]) -> None:
            self.iloc = values

        def __len__(self) -> int:
            return len(self.iloc)

    class FakeHistory:
        def __init__(self, closes: list[float]) -> None:
            self._closes = FakeSeries(closes)

        def get(self, key: str) -> FakeSeries | None:
            if key == "Close":
                return self._closes
            return None

    class FakeTicker:
        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, period: str, interval: str) -> FakeHistory:
            return FakeHistory([100.0, 110.0])

        @property
        def info(self) -> dict:
            raise RuntimeError("metadata failure")

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        FakeTicker,
    )

    snapshot = YFinancePriceProvider().fetch_daily_snapshot("LC")

    assert snapshot is not None
    assert snapshot.currency == "USD"


@pytest.mark.parametrize("currency_value", [None, "", 123])
def test_yfinance_price_provider_ignores_malformed_currency_metadata(
    monkeypatch: pytest.MonkeyPatch,
    currency_value: object,
) -> None:
    class FakeSeries:
        def __init__(self, values: list[float]) -> None:
            self.iloc = values

        def __len__(self) -> int:
            return len(self.iloc)

    class FakeHistory:
        def __init__(self, closes: list[float]) -> None:
            self._closes = FakeSeries(closes)

        def get(self, key: str) -> FakeSeries | None:
            if key == "Close":
                return self._closes
            return None

    class FakeTicker:
        info = {"currency": currency_value}

        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, period: str, interval: str) -> FakeHistory:
            return FakeHistory([100.0, 110.0])

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        FakeTicker,
    )

    snapshot = YFinancePriceProvider().fetch_daily_snapshot("LC")

    assert snapshot is not None
    assert snapshot.currency == "USD"


def test_yfinance_price_provider_strips_whitespace_from_currency_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSeries:
        def __init__(self, values: list[float]) -> None:
            self.iloc = values

        def __len__(self) -> int:
            return len(self.iloc)

    class FakeHistory:
        def __init__(self, closes: list[float]) -> None:
            self._closes = FakeSeries(closes)

        def get(self, key: str) -> FakeSeries | None:
            if key == "Close":
                return self._closes
            return None

    class FakeTicker:
        info = {"currency": "  KRW  "}

        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, period: str, interval: str) -> FakeHistory:
            return FakeHistory([100.0, 110.0])

    monkeypatch.setattr(
        "daily_stock_briefing.adapters.prices.yfinance_adapter.yf.Ticker",
        FakeTicker,
    )

    snapshot = YFinancePriceProvider().fetch_daily_snapshot("LC")

    assert snapshot is not None
    assert snapshot.currency == "KRW"
