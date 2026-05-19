from __future__ import annotations

import argparse
import logging
from pathlib import Path

import yaml

from press_release_collector.collectors.html_collector import collect_html
from press_release_collector.collectors.rss_collector import collect_rss
from press_release_collector.collectors.wire_collector import collect_wire
from press_release_collector.core.dedupe import dedupe_press_releases
from press_release_collector.core.normalize import normalize_press_release
from press_release_collector.core.storage import bulk_upsert_press_releases, init_db

logger = logging.getLogger(__name__)


def run(config_path: Path, db_path: Path) -> dict[str, int]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    companies = payload.get("companies") or []
    if not isinstance(companies, list):
        raise ValueError("companies must be a list")

    init_db(db_path)
    counts: dict[str, int] = {}
    for company in companies:
        if not isinstance(company, dict):
            continue
        ticker = str(company.get("ticker") or "").strip()
        company_name = str(company.get("company_name") or "").strip()
        if not ticker or not company_name:
            continue

        releases = []
        for source in company.get("official_sources") or []:
            if not isinstance(source, dict):
                continue
            source_type = source.get("type")
            url = str(source.get("url") or "").strip()
            if not url:
                continue
            if source_type == "rss":
                releases.extend(collect_rss(ticker, company_name, url))
            elif source_type == "html":
                releases.extend(
                    collect_html(ticker=ticker, company_name=company_name, url=url)
                )
        releases.extend(
            collect_wire(
                ticker,
                company_name,
                [str(q) for q in company.get("wire_queries") or []],
            )
        )
        normalized = [normalize_press_release(item) for item in releases]
        unique = dedupe_press_releases(normalized)
        counts[ticker.upper()] = bulk_upsert_press_releases(db_path, unique)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="src/press_release_collector/config/sources.yaml")
    parser.add_argument("--db", default="data/press_releases.sqlite")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    counts = run(Path(args.config), Path(args.db))
    for ticker, count in counts.items():
        print(f"{ticker}: {count} new press releases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
