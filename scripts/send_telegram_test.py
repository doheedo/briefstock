import os
from pathlib import Path

from dotenv import load_dotenv

from daily_stock_briefing.adapters.telegram.client import TelegramClient


def main() -> int:
    load_dotenv()
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    client = TelegramClient(token, chat_id)
    sample = Path("reports/html/sample-2026-04-24.html")
    if sample.exists():
        client.send_document(sample, "Sample HTML report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
