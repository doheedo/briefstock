from daily_stock_briefing.adapters.llm import openai_compatible
from daily_stock_briefing.adapters.llm.openai_compatible import (
    OpenAICompatibleLlmClassifier,
)
from daily_stock_briefing.domain.enums import DailyPriority, EventCategory, ThesisImpact
from daily_stock_briefing.domain.models import CompanyEvent, SymbolBriefing, WatchlistItem


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"thesis_summary":"LLM 요약: 가이던스 하향은 thesis에 부정적",'
                            '"follow_up_questions":["원문 링크의 수치가 일회성인지 확인"]}'
                        )
                    }
                }
            ]
        }


class _FakeClient:
    def __init__(self, requests, **kwargs) -> None:
        self._requests = requests

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url, headers=None, json=None):
        self._requests.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse()


def _briefing() -> SymbolBriefing:
    return SymbolBriefing(
        watchlist_item=WatchlistItem(
            ticker="LC",
            name="LendingClub",
            market="US",
            thesis="credit quality",
            keywords=["LendingClub"],
            source_priority=["news", "filings", "price"],
        ),
        derived_events=[
            CompanyEvent(
                ticker="LC",
                category=EventCategory.GUIDANCE,
                importance_score=5,
                thesis_impact=ThesisImpact.NEGATIVE,
                summary="Guidance cut",
                evidence=["Guidance cut"],
                source_refs=["https://example.com/original"],
            )
        ],
        thesis_summary="negative: Guidance cut",
        follow_up_questions=["Check source"],
        priority=DailyPriority.HIGH,
    )


def test_openai_compatible_llm_refines_briefing_with_source_context(
    monkeypatch,
) -> None:
    requests = []
    monkeypatch.setattr(
        openai_compatible.httpx,
        "Client",
        lambda **kwargs: _FakeClient(requests, **kwargs),
    )
    client = OpenAICompatibleLlmClassifier(
        api_key="secret",
        base_url="https://api.example.com/v1",
        model="model-1",
    )

    refined = client.refine_briefing(_briefing())

    assert refined.thesis_summary.startswith("LLM 요약")
    assert refined.follow_up_questions == [
        "Check source",
        "원문 링크의 수치가 일회성인지 확인",
    ]
    assert requests[0]["url"] == "https://api.example.com/v1/chat/completions"
    assert requests[0]["json"]["response_format"] == {"type": "json_object"}
    assert "https://example.com/original" in requests[0]["json"]["messages"][1]["content"]


def test_openai_compatible_llm_returns_original_on_bad_response(monkeypatch) -> None:
    class _BadClient(_FakeClient):
        def post(self, url, headers=None, json=None):
            raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(
        openai_compatible.httpx,
        "Client",
        lambda **kwargs: _BadClient([], **kwargs),
    )
    client = OpenAICompatibleLlmClassifier(
        api_key="secret",
        base_url="https://api.example.com/v1",
        model="model-1",
    )
    briefing = _briefing()

    assert client.refine_briefing(briefing) == briefing


def test_openai_compatible_llm_respects_minimum_request_interval(monkeypatch) -> None:
    requests = []
    sleeps = []
    times = iter([100.0, 100.5])
    monkeypatch.setattr(
        openai_compatible.httpx,
        "Client",
        lambda **kwargs: _FakeClient(requests, **kwargs),
    )
    monkeypatch.setattr(openai_compatible.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(openai_compatible.time, "sleep", sleeps.append)
    client = OpenAICompatibleLlmClassifier(
        api_key="secret",
        base_url="https://api.example.com/v1",
        model="model-1",
        rpm_limit=30,
    )

    client.refine_briefing(_briefing())
    client.refine_briefing(_briefing())

    assert sleeps == [1.5]
    assert len(requests) == 2
