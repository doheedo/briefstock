from pathlib import Path

import yaml

from daily_stock_briefing.domain.models import WatchlistItem


def load_watchlist(path: Path) -> list[WatchlistItem]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        raise ValueError("watchlist config is empty")
    if not isinstance(payload, dict):
        raise ValueError("watchlist config must be a mapping")

    raw_watchlist = payload.get("watchlist")
    if raw_watchlist is None:
        raise ValueError("watchlist config must contain a watchlist list")
    if not isinstance(raw_watchlist, list):
        raise ValueError("watchlist must be a list")

    return [WatchlistItem.model_validate(item) for item in raw_watchlist]
