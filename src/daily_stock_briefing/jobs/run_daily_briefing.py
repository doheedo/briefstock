import argparse
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

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
from daily_stock_briefing.renderers.chart_renderer import write_price_chart
from daily_stock_briefing.renderers.html_report import write_html_report
from daily_stock_briefing.renderers.telegram_html import render_telegram_html
from daily_stock_briefing.services.config_loader import load_watchlist
from daily_stock_briefing.services.news_dedupe import dedupe_news
from daily_stock_briefing.services.report_builder import build_symbol_briefing
from daily_stock_briefing.services.yellowbrick_enrichment import enrich_symbol_with_yellowbrick


_LOGGER = logging.getLogger(__name__)


def configure_logging(
    *,
    log_file: Path = Path("logs/briefstock.log"),
    level: int = logging.INFO,
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
) -> None:
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not any(getattr(handler, "_briefstock_console", False) for handler in root_logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler._briefstock_console = True
        root_logger.addHandler(console_handler)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    target = str(log_file.resolve())
    if not any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == target
        for handler in root_logger.handlers
    ):
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_environment() -> None:
    env_path = _project_root() / ".env"
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path, override=False)
    load_dotenv(override=False)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _benchmark_for_market(market: str) -> str:
    if market.upper().startswith("KR"):
        return "^KS200"
    return "^GSPC"


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
    if item.market.upper().startswith("KR"):
        # dart_provider must be pre-constructed by the caller so that
        # _corp_codes_by_stock cache is shared across all tickers in a run.
        # Falling back to a new instance here would re-download the corpcode
        # ZIP on every ticker call.
        if dart_provider is None:
            return []
        return dart_provider.fetch_filings(item)
    if item.market.upper() in {"US", "USA", "CA", "CANADA"}:
        if sec_provider is None:
            user_agent = os.getenv("SEC_USER_AGENT") or (
                "DailyStockBriefing/0.1 contact@example.com"
            )
            sec_provider = SecFilingProvider(user_agent=user_agent)
        return sec_provider.fetch_filings(item)
    return []


def _build_news_provider() -> HttpNewsProvider | None:
    base_url = os.getenv("NEWS_API_BASE_URL")
    api_key = os.getenv("NEWS_API_KEY")
    if not base_url or not api_key:
        return None
    return HttpNewsProvider(base_url=base_url, api_key=api_key)


def _yellowbrick_enabled() -> bool:
    flag = (os.getenv("YELLOWBRICK_ENABLED") or "").strip().lower()
    return flag in ("1", "true", "yes", "on")


def _build_llm_classifier() -> OpenAICompatibleLlmClassifier | None:
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider in {"", "auto", "nvidia"} and os.getenv("NVIDIA_API_KEY"):
        model = os.getenv("NVIDIA_LLM_MODEL") or "deepseek-ai/deepseek-v4-pro"
        if model:
            return OpenAICompatibleLlmClassifier(
                api_key=os.environ["NVIDIA_API_KEY"],
                base_url="https://integrate.api.nvidia.com/v1",
                model=model,
                rpm_limit=int(os.getenv("LLM_RPM_LIMIT") or "40"),
            )
    if provider in {"", "auto"} and os.getenv("GROQ_API_KEY"):
        return OpenAICompatibleLlmClassifier(
            api_key=os.environ["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
            model=os.getenv("LLM_MODEL") or "llama-3.1-8b-instant",
            rpm_limit=int(os.getenv("LLM_RPM_LIMIT") or "30"),
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

    configure_logging()
    _load_environment()
    watchlist = load_watchlist(Path(args.watchlist))
    if args.group:
        _LOGGER.info("Group filter is ignored in unified delivery mode: %s", args.group)
    price_provider = YFinancePriceProvider()
    news_provider = _build_news_provider()
    llm_classifier = _build_llm_classifier()
    dart_api_key = os.getenv("DART_API_KEY")
    dart_provider = DartFilingProvider(dart_api_key) if dart_api_key else None
    sec_provider = SecFilingProvider(
        user_agent=os.getenv("SEC_USER_AGENT")
        or "DailyStockBriefing/0.1 contact@example.com"
    )

    briefings = []
    warnings: list[str] = []
    for item in watchlist:
        try:
            price = price_provider.fetch_daily_snapshot(
                item.ticker,
                benchmark_ticker=_benchmark_for_market(item.market),
            )
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
        if _yellowbrick_enabled():
            briefing = enrich_symbol_with_yellowbrick(briefing, llm_classifier)
        briefings.append(briefing)

    default_summary = "관심종목 소스 기반 데일리 변화 요약."
    market_summary = default_summary
    if llm_classifier is not None and briefings:
        market_summary = llm_classifier.summarize_report(briefings, default_summary)

    report = DailyBriefingReport(
        run_date=args.date,
        market_summary=market_summary,
        symbol_briefings=briefings,
        delivery_metadata={"warnings": "\n".join(warnings)} if warnings else {},
    )

    output_stem = args.date
    html_path = write_html_report(report, Path("reports/html") / f"{output_stem}.html")
    json_path = Path("reports/json") / f"{output_stem}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    if args.skip_telegram:
        _LOGGER.info("Telegram skipped: --skip-telegram")
    elif not os.getenv("TELEGRAM_BOT_TOKEN"):
        _LOGGER.info("Telegram skipped: TELEGRAM_BOT_TOKEN not set")
    elif not os.getenv("TELEGRAM_CHAT_ID"):
        _LOGGER.info("Telegram skipped: TELEGRAM_CHAT_ID not set")
    else:
        from daily_stock_briefing.adapters.telegram.client import TelegramClient

        client = TelegramClient(
            os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
        )
        client.send_html(render_telegram_html(report))
        client.send_document(html_path, caption=f"Daily report {args.date}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
