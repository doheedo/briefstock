import argparse
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from daily_stock_briefing.adapters.filings.dart_adapter import DartFilingProvider
from daily_stock_briefing.adapters.filings.sec_adapter import SecFilingProvider
from daily_stock_briefing.adapters.llm.openai_compatible import (
    OpenAICompatibleLlmClassifier,
)
from daily_stock_briefing.adapters.news.http_news_adapter import HttpNewsProvider
from daily_stock_briefing.adapters.prices.yfinance_adapter import YFinancePriceProvider
from daily_stock_briefing.domain.enums import DailyPriority
from daily_stock_briefing.domain.models import DailyBriefingReport, FilingItem, NewsItem
from daily_stock_briefing.renderers.chart_renderer import (
    safe_ticker_filename,
    write_price_chart,
)
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


def _fetch_filings(
    item,
    *,
    dart_provider: DartFilingProvider | None = None,
    sec_provider: SecFilingProvider | None = None,
) -> list[FilingItem]:
    if item.market.upper().startswith("KR") and os.getenv("DART_API_KEY"):
        provider = dart_provider or DartFilingProvider(os.environ["DART_API_KEY"])
        return provider.fetch_filings(item)
    if item.market.upper() in {"US", "USA", "CA", "CANADA"}:
        provider = sec_provider
        if provider is None:
            user_agent = os.getenv("SEC_USER_AGENT") or (
                "DailyStockBriefing/0.1 contact@example.com"
            )
            provider = SecFilingProvider(user_agent=user_agent)
        return provider.fetch_filings(item)
    return []


def _build_news_provider() -> HttpNewsProvider | None:
    base_url = os.getenv("NEWS_API_BASE_URL")
    api_key = os.getenv("NEWS_API_KEY")
    if not base_url or not api_key:
        return None
    return HttpNewsProvider(base_url=base_url, api_key=api_key)


def _build_llm_classifier() -> OpenAICompatibleLlmClassifier | None:
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider in {"", "auto"} and os.getenv("GROQ_API_KEY"):
        return OpenAICompatibleLlmClassifier(
            api_key=os.environ["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
            model=os.getenv("LLM_MODEL") or "llama-3.1-8b-instant",
            rpm_limit=int(os.getenv("LLM_RPM_LIMIT") or "30"),
        )
    if provider in {"", "auto", "nvidia"} and os.getenv("NVIDIA_API_KEY"):
        model = os.getenv("NVIDIA_LLM_MODEL") or os.getenv("LLM_MODEL")
        if model:
            return OpenAICompatibleLlmClassifier(
                api_key=os.environ["NVIDIA_API_KEY"],
                base_url="https://integrate.api.nvidia.com/v1",
                model=model,
                rpm_limit=int(os.getenv("LLM_RPM_LIMIT") or "40"),
            )
    if provider in {"none", "false", "off", "disabled"}:
        return None

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_API_BASE_URL")
    model = os.getenv("LLM_MODEL")
    if api_key and base_url and model:
        return OpenAICompatibleLlmClassifier(
            api_key=api_key,
            base_url=base_url,
            model=model,
            rpm_limit=int(os.getenv("LLM_RPM_LIMIT") or "0") or None,
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=_today())
    parser.add_argument("--watchlist", default="config/watchlist.yaml")
    parser.add_argument("--group", default=None)
    parser.add_argument("--skip-telegram", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv()
    watchlist = load_watchlist(Path(args.watchlist))
    if args.group:
        watchlist = [item for item in watchlist if item.group == args.group]
    price_provider = YFinancePriceProvider()
    news_provider = _build_news_provider()
    llm_classifier = _build_llm_classifier()
    dart_provider = (
        DartFilingProvider(os.environ["DART_API_KEY"])
        if os.getenv("DART_API_KEY")
        else None
    )
    sec_provider = SecFilingProvider(
        user_agent=os.getenv("SEC_USER_AGENT")
        or "DailyStockBriefing/0.1 contact@example.com"
    )

    briefings = []
    warnings: list[str] = []
    for item in watchlist:
        try:
            price = price_provider.fetch_daily_snapshot(item.ticker)
        except Exception as exc:  # pragma: no cover - defensive job boundary
            warnings.append(f"{item.ticker}: price unavailable ({exc})")
            price = None
        if price is not None:
            try:
                closes = price_provider.get_cached_closes(item.ticker)
                if closes:
                    chart_path = write_price_chart(
                        ticker=item.ticker,
                        name=item.name,
                        closes=closes,
                        output_dir=Path("reports/charts") / args.date,
                    )
                    if chart_path is not None:
                        price = price.model_copy(
                            update={
                                "chart_path": (
                                    f"../charts/{args.date}/{chart_path.name}"
                                )
                            }
                        )
                    else:
                        warnings.append(f"{item.ticker}: chart unavailable")
            except Exception as exc:  # pragma: no cover - defensive job boundary
                warnings.append(f"{item.ticker}: chart unavailable ({exc})")

        try:
            news = dedupe_news(_fetch_news(item, news_provider))
        except Exception as exc:  # pragma: no cover - defensive job boundary
            warnings.append(f"{item.ticker}: news unavailable ({exc})")
            news = []

        try:
            filings = _fetch_filings(
                item,
                dart_provider=dart_provider,
                sec_provider=sec_provider,
            )
        except Exception as exc:  # pragma: no cover - defensive job boundary
            warnings.append(f"{item.ticker}: filings unavailable ({exc})")
            filings = []

        briefing = build_symbol_briefing(item, price, news, filings)
        if (
            llm_classifier is not None
            and briefing.derived_events
            and briefing.priority != DailyPriority.LOW
        ):
            briefing = llm_classifier.refine_briefing(briefing)
        briefings.append(briefing)

    report = DailyBriefingReport(
        run_date=args.date,
        market_summary=(
            "관심종목 소스 기반 데일리 변화 요약."
            + (f" 그룹: {args.group}." if args.group else "")
        ),
        symbol_briefings=briefings,
        delivery_metadata={"warnings": "\n".join(warnings)} if warnings else {},
    )

    output_stem = (
        f"{args.date}-{safe_ticker_filename(args.group)}" if args.group else args.date
    )
    html_path = write_html_report(report, Path("reports/html") / f"{output_stem}.html")
    json_path = Path("reports/json") / f"{output_stem}.json"
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
