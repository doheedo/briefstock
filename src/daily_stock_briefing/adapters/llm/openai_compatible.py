import json
import time
from typing import Any

import httpx

from daily_stock_briefing.adapters.llm.base import LlmClassifier
from daily_stock_briefing.domain.models import SymbolBriefing


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
        except Exception:
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

    def _respect_rate_limit(self) -> None:
        if self._min_interval_seconds <= 0:
            return
        now = time.monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            if elapsed < self._min_interval_seconds:
                time.sleep(self._min_interval_seconds - elapsed)
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
