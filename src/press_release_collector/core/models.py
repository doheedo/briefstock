from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel


class PressRelease(BaseModel):
    ticker: str
    company_name: str
    title: str
    url: str
    published_at: str | None = None
    source_name: str
    source_type: str
    summary: str | None = None
    content: str | None = None
    uid: str = ""
    collected_at: str

    @classmethod
    def from_raw(
        cls,
        *,
        ticker: str,
        company_name: str,
        title: str,
        url: str,
        source_name: str,
        source_type: str,
        published_at: str | None = None,
        summary: str | None = None,
        content: str | None = None,
        collected_at: str | None = None,
        uid: str = "",
    ) -> "PressRelease":
        return cls(
            ticker=ticker,
            company_name=company_name,
            title=title,
            url=url,
            published_at=published_at,
            source_name=source_name,
            source_type=source_type,
            summary=summary,
            content=content,
            uid=uid,
            collected_at=collected_at or datetime.now(UTC).isoformat(),
        )
