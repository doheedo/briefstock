import json
import logging
import time
from typing import Any

import httpx

from daily_stock_briefing.adapters.llm.base import LlmClassifier
from daily_stock_briefing.domain.models import CompanyDisclosure, SymbolBriefing

logger = logging.getLogger(__name__)

TRANSLATION_BATCH_SIZE = 2
LLM_RATE_LIMIT_COOLDOWN_SECONDS = 60.0
LLM_AUTH_FAILURE_COOLDOWN_SECONDS = 3600.0
YELLOWBRICK_RETRY_CONTENT_LIMIT = 3000


class _ProviderUnavailable(Exception):
    """Raised when the upstream LLM provider should be skipped for this run."""


class _RateLimitExceeded(_ProviderUnavailable):
    """Raised when the upstream LLM provider rejects more requests for now."""


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
        self._cooldown_until: float = 0.0

    def refine_briefing(self, briefing: SymbolBriefing) -> SymbolBriefing:
        payload = self._request_payload(briefing)
        try:
            data = self._request_chat_completion(payload)
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
            data = self._request_chat_completion(payload)
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
            data = self._request_chat_completion(
                payload,
                compact_user_content_limit=YELLOWBRICK_RETRY_CONTENT_LIMIT,
            )
            content = data["choices"][0]["message"]["content"]
            if content and isinstance(content, str):
                out = content.strip()
                return out if out else None
        except Exception as exc:
            logger.warning("LLM Yellowbrick summary failed: %s", exc)
            return None
        return None

    def translate_company_disclosures(
        self,
        disclosures: list[CompanyDisclosure],
    ) -> list[CompanyDisclosure]:
        targets = [
            (index, disclosure)
            for index, disclosure in enumerate(disclosures)
            if disclosure.summary and not _contains_korean(disclosure.summary)
        ]
        if not targets:
            return disclosures

        translations: dict[int, str] = {}
        for start in range(0, len(targets), TRANSLATION_BATCH_SIZE):
            batch = targets[start : start + TRANSLATION_BATCH_SIZE]
            try:
                batch_translations = self._translate_company_disclosure_batch(batch)
            except _ProviderUnavailable:
                break
            if batch_translations is not None:
                translations.update(batch_translations)
                continue
            if len(batch) == 1:
                continue
            for target in batch:
                try:
                    single_translations = self._translate_company_disclosure_batch([target])
                except _ProviderUnavailable:
                    return _apply_company_disclosure_translations(disclosures, translations)
                if single_translations:
                    translations.update(single_translations)

        return _apply_company_disclosure_translations(disclosures, translations)

    def _translate_company_disclosure_batch(
        self,
        targets: list[tuple[int, CompanyDisclosure]],
    ) -> dict[int, str] | None:
        payload = {
            "model": self._model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 투자 브리핑 편집자입니다. 회사 공식 보도자료 요약을 "
                        "자연스러운 한국어 한 문장으로 번역하세요. 숫자, 회사명, 제품명, "
                        "고유명사는 보존하고 새 사실을 추가하지 마세요. JSON만 반환하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "items": [
                                {
                                    "index": index,
                                    "title": disclosure.title,
                                    "summary": (disclosure.summary or "")[:1200],
                                }
                                for index, disclosure in targets
                            ],
                            "instruction": (
                                "Return JSON shaped as "
                                '{"summaries":[{"index":0,"summary_ko":"한국어 번역"}]}.'
                            ),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        try:
            data = self._request_chat_completion(payload)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("LLM company disclosure translation rate-limited: %s", exc)
                raise _RateLimitExceeded from exc
            logger.warning("LLM company disclosure translation failed: %s", exc)
            return None
        except _ProviderUnavailable as exc:
            logger.warning("LLM company disclosure translation unavailable: %s", exc)
            raise
        except Exception as exc:
            logger.warning("LLM company disclosure translation failed: %s", exc)
            return None

        parsed = _extract_json_content(data)
        summaries = parsed.get("summaries") if parsed else None
        if not isinstance(summaries, list):
            return None

        translations: dict[int, str] = {}
        for item in summaries:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            summary = item.get("summary_ko")
            if (
                isinstance(index, int)
                and isinstance(summary, str)
                and summary.strip()
                and _contains_korean(summary)
            ):
                translations[index] = summary.strip()
        return translations or None

    def _request_chat_completion(
        self,
        payload: dict[str, Any],
        *,
        compact_user_content_limit: int | None = None,
    ) -> dict[str, Any]:
        attempts = [payload]
        if compact_user_content_limit:
            attempts.append(
                _compact_last_user_message_payload(payload, compact_user_content_limit)
            )
        last_error: Exception | None = None
        for attempt_index, request_payload in enumerate(attempts):
            self._raise_if_llm_on_cooldown()
            self._respect_rate_limit()
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(
                        f"{self._base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=request_payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code == 429:
                    self._cooldown_until = (
                        time.monotonic() + LLM_RATE_LIMIT_COOLDOWN_SECONDS
                    )
                    raise _RateLimitExceeded("LLM provider rate limited") from exc
                if exc.response.status_code in {401, 403}:
                    self._cooldown_until = (
                        time.monotonic() + LLM_AUTH_FAILURE_COOLDOWN_SECONDS
                    )
                    raise _ProviderUnavailable(
                        "LLM provider auth/permission failed; cooling down"
                    ) from exc
                if (
                    exc.response.status_code == 413
                    and compact_user_content_limit
                    and attempt_index == 0
                ):
                    logger.warning(
                        "LLM payload too large; retrying with compact prompt."
                    )
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("No LLM response was produced.")

    def _raise_if_llm_on_cooldown(self) -> None:
        remaining = self._cooldown_until - time.monotonic()
        if remaining > 0:
            raise _ProviderUnavailable(
                f"LLM provider is cooling down for {remaining:.0f}s"
            )

    def _respect_rate_limit(self) -> None:
        if self._min_interval_seconds <= 0:
            return
        now = time.monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            if elapsed < self._min_interval_seconds:
                time.sleep(self._min_interval_seconds - elapsed)
                now = time.monotonic()
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
                        "these keys: thesis_summary, follow_up_questions. "
                        "Never output generic questions like 'Does this change the core thesis today?'. "
                        "When mentioning relative weakness, include actionable checks (benchmark correlation, filing/news linkage). "
                        "If insider filings are present, ask for net buy/sell versus annual compensation ratio and flag >=50%. "
                        "If 8-K is present, ask to summarize concrete item-level disclosures."
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


def _compact_last_user_message_payload(
    payload: dict[str, Any],
    content_limit: int,
) -> dict[str, Any]:
    compact_payload = {**payload}
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return compact_payload
    compact_messages = [dict(message) for message in messages if isinstance(message, dict)]
    for message in reversed(compact_messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str) and len(content) > content_limit:
            prefix, separator, body = content.partition("\n\n")
            compact_body = body[-content_limit:] if separator else content[-content_limit:]
            message["content"] = (
                f"{prefix}\n\n{compact_body}" if separator else compact_body
            )
        break
    compact_payload["messages"] = compact_messages
    return compact_payload


def _apply_company_disclosure_translations(
    disclosures: list[CompanyDisclosure],
    translations: dict[int, str],
) -> list[CompanyDisclosure]:
    if not translations:
        return disclosures

    out = [*disclosures]
    for index, summary in translations.items():
        if 0 <= index < len(out):
            out[index] = out[index].model_copy(update={"summary": summary})
    return out


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


def _contains_korean(text: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in text)
