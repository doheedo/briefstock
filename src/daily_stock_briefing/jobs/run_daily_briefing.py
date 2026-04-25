import argparse
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from daily_stock_briefing.adapters.filings.dart_adapter import DartFilingProvider
from daily_stock_briefing.adapters.filings.sec_adapter import SecFilingProvider
from daily_stock_briefing.adapters.news.http_news_adapter import HttpNewsProvider
from daily_stock_briefing.adapters.prices.yfinance_adapter import YFinancePriceProvider
from daily_stock_briefing.domain.models import DailyBriefingReport, FilingItem, NewsItem
from daily_stock_briefing.renderers.html_report import write_html_report
from daily_stock_briefing.renderers.telegram_html import render_telegram_html
from daily_stock_briefing.services.config_loader import load_watchlist
from daily_stock_briefing.services.news_dedupe import dedupe_news
from daily_stock_briefing.services.report_builder import build_symbol_briefing


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _fetch_news(item, provider: HttpNewsProvider | None) -> list[NewsItem]:
    if provider is None:
        return []
    return provider.fetch_news(item)


def _fetch_filings(item) -> list[FilingItem]:
    if item.market.upper().startswith("KR") and os.getenv("DART_API_KEY"):
        return DartFilingProvider(os.environ["DART_API_KEY"]).fetch_filings(item)
    if item.market.upper() in {"US", "USA", "CA", "CANADA"}:
        user_agent = os.getenv("SEC_USER_AGENT") or (
            "DailyStockBriefing/0.1 contact@example.com"
        )
        return SecFilingProvider(user_agent=user_agent).fetch_filings(item)
    return []


def _build_news_provider() -> HttpNewsProvider | None:
    base_url = os.getenv("NEWS_API_BASE_URL")
    api_key = os.getenv("NEWS_API_KEY")
    if not base_url or not api_key:
        return None
    return HttpNewsProvider(base_url=base_url, api_key=api_key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=_today())
    parser.add_argument("--watchlist", default="config/watchlist.yaml")
    parser.add_argument("--skip-telegram", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv()
    watchlist = load_watchlist(Path(args.watchlist))
    price_provider = YFinancePriceProvider()
    news_provider = _build_news_provider()

    briefings = []
    warnings: list[str] = []
    for item in watchlist:
        try:
            price = price_provider.fetch_daily_snapshot(item.ticker)
        except Exception as exc:  # pragma: no cover - defensive job boundary
            warnings.append(f"{item.ticker}: price unavailable ({exc})")
            price = None

        try:
            news = dedupe_news(_fetch_news(item, news_provider))
        except Exception as exc:  # pragma: no cover - defensive job boundary
            warnings.append(f"{item.ticker}: news unavailable ({exc})")
            news = []

        try:
            filings = _fetch_filings(item)
        except Exception as exc:  # pragma: no cover - defensive job boundary
            warnings.append(f"{item.ticker}: filings unavailable ({exc})")
            filings = []

        briefings.append(build_symbol_briefing(item, price, news, filings))

    report = DailyBriefingReport(
        run_date=args.date,
        market_summary="Daily delta briefing generated from watchlist sources.",
        symbol_briefings=briefings,
        delivery_metadata={"warnings": "\n".join(warnings)} if warnings else {},
    )

    html_path = write_html_report(report, Path("reports/html") / f"{args.date}.html")
    json_path = Path("reports/json") / f"{args.date}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    if not args.skip_telegram and os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv(
        "TELEGRAM_CHAT_ID"
    ):
        from daily_stock_briefing.adapters.telegram.client import TelegramClient

        client = TelegramClient(
            os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
        )
        client.send_html(render_telegram_html(report))
        client.send_document(html_path, caption=f"Daily report {args.date}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
