from pathlib import Path
from typing import Any

import httpx


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str, timeout: float = 15.0) -> None:
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._chat_id = chat_id
        self._timeout = timeout

    def send_html(self, text: str) -> dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}

    def send_document(self, path: Path, caption: str) -> dict[str, Any]:
        with httpx.Client(timeout=max(self._timeout, 30.0)) as client:
            with path.open("rb") as handle:
                response = client.post(
                    f"{self._base_url}/sendDocument",
                    data={"chat_id": self._chat_id, "caption": caption},
                    files={"document": (path.name, handle, "text/html")},
                )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
