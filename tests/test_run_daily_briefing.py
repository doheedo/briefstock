import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from daily_stock_briefing.adapters.filings import dart_adapter, sec_adapter
from daily_stock_briefing.adapters.filings.base import build_filing_item
from daily_stock_briefing.adapters.filings.dart_adapter import DartFilingProvider
from daily_stock_briefing.adapters.filings.sec_adapter import (
    SecFilingProvider,
    normalize_sec_filing,
)
from daily_stock_briefing.domain.models import FilingItem, WatchlistItem


def _load_sample_filings() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "fixtures" / "sample_filings.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _make_watchlist_item(ticker: str, market: str = "US") -> WatchlistItem:
    return WatchlistItem(
        ticker=ticker,
        name=f"{ticker} Corp",
        market=market,
        thesis="Track filing changes",
        keywords=["filing"],
    )


def _make_dart_lookup_zip(xml_text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("CORPCODE.xml", xml_text)
    return buffer.getvalue()


class _FakeResponse:
    def __init__(
        self,
        *,
        json_data: Any | None = None,
        content: bytes = b"",
        status_code: int = 200,
    ) -> None:
        self._json_data = json_data
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._json_data


class _FakeClient:
    def __init__(
        self,
        responses: list[_FakeResponse],
        requests: list[dict[str, Any]],
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> None:
        self._responses = responses
        self._requests = requests
        self.headers = headers or {}
        self.timeout = timeout

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeResponse:
        self._requests.append(
            {
                "url": url,
                "params": params,
                "headers": self.headers,
                "timeout": self.timeout,
            }
        )
        return self._responses.pop(0)


def test_normalize_sec_filing_maps_common_fields() -> None:
    raw = {
        "accessionNumber": "0000001",
        "cik": "0001409970",
        "form": "8-K",
        "filingDate": "2026-04-24",
        "primaryDocDescription": "Current report",
        "primaryDocument": "doc.htm",
    }

    item = normalize_sec_filing("LC", raw)

    assert item.id == "0000001"
    assert item.ticker == "LC"
    assert item.filing_type == "8-K"
    assert item.title == "Current report"
    assert item.source_system == "SEC"
    assert item.filed_at == datetime(2026, 4, 24, tzinfo=timezone.utc)
    assert (
        item.filing_url
        == "https://www.sec.gov/Archives/edgar/data/1409970/0000001/doc.htm"
    )
    assert item.raw_excerpt == "Current report"


def test_build_filing_item_assembles_common_fields() -> None:
    item = build_filing_item(
        id="filing-1",
        ticker="LC",
        filing_type="8-K",
        title="Current report",
        filed_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        filing_url="https://example.com/filing-1",
        source_system="SEC",
        raw_excerpt="Current report",
    )

    assert item == FilingItem(
        id="filing-1",
        ticker="LC",
        filing_type="8-K",
        title="Current report",
        filed_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        filing_url="https://example.com/filing-1",
        source_system="SEC",
        raw_excerpt="Current report",
    )


def test_sec_provider_fetch_filings_looks_up_cik_before_submissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = _load_sample_filings()
    requests: list[dict[str, Any]] = []
    responses = [
        _FakeResponse(json_data=sample["sec_lookup"]),
        _FakeResponse(json_data=sample["sec_submissions"]),
    ]

    monkeypatch.setattr(
        sec_adapter.httpx,
        "Client",
        lambda **kwargs: _FakeClient(responses, requests, **kwargs),
    )

    provider = SecFilingProvider(user_agent="task4-test-agent")
    filings = provider.fetch_filings(_make_watchlist_item("LC"))

    assert [request["url"] for request in requests] == [
        "https://www.sec.gov/files/company_tickers.json",
        "https://data.sec.gov/submissions/CIK0001409970.json",
    ]
    assert requests[0]["headers"] == {"User-Agent": "task4-test-agent"}
    assert len(filings) == 1
    assert filings[0].id == "000140997026000001"
    assert filings[0].ticker == "LC"
    assert filings[0].source_system == "SEC"


def test_sec_provider_returns_empty_when_ticker_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    responses = [_FakeResponse(json_data={"0": {"ticker": "MSFT", "cik_str": 789019}})]

    monkeypatch.setattr(
        sec_adapter.httpx,
        "Client",
        lambda **kwargs: _FakeClient(responses, requests, **kwargs),
    )

    provider = SecFilingProvider(user_agent="task4-test-agent")

    assert provider.fetch_filings(_make_watchlist_item("LC")) == []
    assert [request["url"] for request in requests] == [
        "https://www.sec.gov/files/company_tickers.json"
    ]


def test_sec_provider_skips_malformed_recent_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = _load_sample_filings()
    responses = [
        _FakeResponse(json_data=sample["sec_lookup"]),
        _FakeResponse(json_data=sample["sec_malformed_submissions"]),
    ]

    monkeypatch.setattr(
        sec_adapter.httpx,
        "Client",
        lambda **kwargs: _FakeClient(responses, [], **kwargs),
    )

    provider = SecFilingProvider(user_agent="task4-test-agent")
    filings = provider.fetch_filings(_make_watchlist_item("LC"))

    assert len(filings) == 1
    assert filings[0].id == "000140997026000001"


def test_dart_provider_fetch_filings_looks_up_corp_code_before_list_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = _load_sample_filings()
    requests: list[dict[str, Any]] = []
    responses = [
        _FakeResponse(content=_make_dart_lookup_zip(sample["dart_lookup_xml"])),
        _FakeResponse(json_data=sample["dart_list"]),
    ]

    monkeypatch.setattr(
        dart_adapter.httpx,
        "Client",
        lambda **kwargs: _FakeClient(responses, requests, **kwargs),
    )

    provider = DartFilingProvider(api_key="dart-test-key")
    filings = provider.fetch_filings(_make_watchlist_item("012700", market="KRX"))

    assert requests == [
        {
            "url": "https://opendart.fss.or.kr/api/corpCode.xml",
            "params": {"crtfc_key": "dart-test-key"},
            "headers": {},
            "timeout": 10.0,
        },
        {
            "url": "https://opendart.fss.or.kr/api/list.json",
            "params": {
                "crtfc_key": "dart-test-key",
                "corp_code": "00126380",
                "page_count": 5,
            },
            "headers": {},
            "timeout": 10.0,
        },
    ]
    assert len(filings) == 1
    assert all(isinstance(filing, FilingItem) for filing in filings)
    assert filings[0].id == "20260424000001"
    assert filings[0].ticker == "012700"
    assert (
        filings[0].filing_url
        == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260424000001"
    )
    assert filings[0].source_system == "DART"


def test_dart_provider_returns_empty_when_corp_code_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    missing_lookup_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?><result>"
        "<list><corp_code>00126380</corp_code><stock_code>005930</stock_code></list>"
        "</result>"
    )
    responses = [_FakeResponse(content=_make_dart_lookup_zip(missing_lookup_xml))]

    monkeypatch.setattr(
        dart_adapter.httpx,
        "Client",
        lambda **kwargs: _FakeClient(responses, requests, **kwargs),
    )

    provider = DartFilingProvider(api_key="dart-test-key")

    assert provider.fetch_filings(_make_watchlist_item("012700", market="KRX")) == []
    assert [request["url"] for request in requests] == [
        "https://opendart.fss.or.kr/api/corpCode.xml"
    ]


def test_dart_provider_skips_malformed_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = _load_sample_filings()
    responses = [
        _FakeResponse(content=_make_dart_lookup_zip(sample["dart_lookup_xml"])),
        _FakeResponse(json_data=sample["dart_malformed_list"]),
    ]

    monkeypatch.setattr(
        dart_adapter.httpx,
        "Client",
        lambda **kwargs: _FakeClient(responses, [], **kwargs),
    )

    provider = DartFilingProvider(api_key="dart-test-key")
    filings = provider.fetch_filings(_make_watchlist_item("012700", market="KRX"))

    assert len(filings) == 1
    assert filings[0].id == "20260424000001"
