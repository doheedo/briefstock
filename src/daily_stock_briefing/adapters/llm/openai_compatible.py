import json
import logging
import time
from typing import Any

import httpx

from daily_stock_briefing.adapters.llm.base import LlmClassifier
from daily_stock_briefing.domain.models import SymbolBriefing

logger = logging.getLogger(__name__)


class OpenAICompatibleLlmClassifier(LlmClassifier):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 20.0,
        rpm_limit: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._min_interval_seconds = 60.0 / rpm_limit if rpm_limit else 0.0
        self._last_request_at: float | None = None

    def refine_briefing(self, briefing: SymbolBriefing) -> SymbolBriefing:
        payload = self._request_payload(briefing)
        try:
            self._respect_rate_limit()
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("LLM briefing refinement failed: %s", exc)
            return briefing

        parsed = _extract_json_content(data)
        if not parsed:
            return briefing

        thesis_summary = parsed.get("thesis_summary")
        follow_up_questions = parsed.get("follow_up_questions")
        if not isinstance(thesis_summary, str) or not thesis_summary.strip():
            return briefing
        if not isinstance(follow_up_questions, list) or not all(
            isinstance(item, str) and item.strip() for item in follow_up_questions
        ):
            follow_up_questions = briefing.follow_up_questions

        merged_questions = [*briefing.follow_up_questions]
        for question in follow_up_questions:
            question = question.strip()
            if question not in merged_questions:
                merged_questions.append(question)

        return briefing.model_copy(
            update={
                "thesis_summary": thesis_summary.strip(),
                "follow_up_questions": merged_questions[:4],
            }
        )

    def summarize_report(self, briefings: list[SymbolBriefing], default_summary: str) -> str:
        items = []
        for b in briefings:
            if b.thesis_summary and b.thesis_summary != "No thesis-relevant update.":
                items.append(f"[{b.watchlist_item.ticker}] {b.thesis_summary}")
        if not items:
            return default_summary

        payload = {
            "model": self._model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 금융 애널리스트입니다. 아래 제공된 각 종목별 주요 업데이트 내용 전체를 읽고, "
                        "가장 중요한 핵심 내용만 추려서 전체 브리핑 요약을 딱 3줄로 작성해주세요. "
                        "마크다운이나 특수문자 없이 평문으로 각 줄을 줄바꿈하여 3줄로 반환하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": "\n".join(items),
                },
            ],
        }

        try:
            self._respect_rate_limit()
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if content and isinstance(content, str):
                    return content.strip()
        except Exception as exc:
            logger.warning("LLM report summary failed: %s", exc)
            pass

        return default_summary

    def summarize_yellowbrick_pitch(
        self,
        english_text: str,
        *,
        title: str | None = None,
    ) -> str | None:
        """Short Korean summary of an external pitch article; returns None on failure."""
        text = english_text.strip()
        if not text:
            return None
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 한국어로 간결한 투자 브리핑을 씁니다. "
                        "주어진 영어 본문을 바탕으로 Yellowbrick/외부 피칭 요지를 "
                        "4~6문장 한국어로 요약하세요. 새 사실을 지어내지 마세요."
                    ),
                },
                {
                    "role": "user",
                    "content": (f"제목: {title}\n\n" if title else "") + text[:14000],
                },
            ],
        }
        try:
            self._respect_rate_limit()
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if content and isinstance(content, str):
                    out = content.strip()
                    return out if out else None
        except Exception as exc:
            logger.warning("LLM Yellowbrick summary failed: %s", exc)
            return None
        return None

    def _respect_rate_limit(self) -> None:
        if self._min_interval_seconds <= 0:
            return
        now = time.monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            if elapsed < self._min_interval_seconds:
                time.sleep(self._min_interval_seconds - elapsed)
        # Timestamp is recorded before the actual HTTP request intentionally.
        # This ensures the interval is measured from when we *start* sending,
        # not when the response arrives, so back-to-back calls never exceed
        # the configured RPM cap even if individual requests complete quickly.
        self._last_request_at = now

    def _request_payload(self, briefing: SymbolBriefing) -> dict[str, Any]:
        source_items = []
        for event in briefing.derived_events[:5]:
            source_items.append(
                {
                    "category": event.category.value,
                    "importance_score": event.importance_score,
                    "thesis_impact": event.thesis_impact.value,
                    "summary": event.summary,
                    "evidence": event.evidence,
                    "source_refs": event.source_refs,
                }
            )

        return {
            "model": self._model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You write concise Korean daily stock briefings. "
                        "Summarize only the new information. Preserve uncertainty. "
                        "Do not invent facts or URLs. Return JSON only with exactly "
                        "these keys: thesis_summary, follow_up_questions."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "ticker": briefing.watchlist_item.ticker,
                            "name": briefing.watchlist_item.name,
                            "thesis": briefing.watchlist_item.thesis,
                            "priority": briefing.priority.value,
                            "current_summary": briefing.thesis_summary,
                            "events": source_items,
                            "instruction": (
                                "Return only a JSON object shaped like "
                                '{"thesis_summary":"short Korean summary",'
                                '"follow_up_questions":["question 1","question 2"]}. '
                                "Do not echo this input."
                            ),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }


def _extract_json_content(data: Any) -> dict[str, Any] | None:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(content, str):
        return None
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
