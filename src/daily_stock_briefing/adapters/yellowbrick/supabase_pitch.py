"""Fetch stock_pitch rows from Yellowbrick's Supabase project (public anon key from web client)."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import httpx

# Default URL + anon JWT are exposed in joinyellowbrick.com static JS (same as the browser client).
_DEFAULT_SUPABASE_URL = "https://ddnuweodkbrqyobdgljg.supabase.co"
_DEFAULT_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRkbnV3ZW9ka2JycXlvYmRnbGpnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDY4MjgwNTAsImV4cCI6MjAyMjQwNDA1MH0."
    "yXvWB9an7dFbrLDF4Xt2tIyXuyp6S_fp7XgyT_4a6wM"
)


def _rest_headers() -> dict[str, str]:
    key = os.getenv("YELLOWBRICK_SUPABASE_ANON_KEY") or _DEFAULT_ANON_KEY
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def fetch_latest_pitch_row(
    ticker_base: str,
    *,
    days: int = 30,
    timeout: float = 20.0,
) -> dict[str, Any] | None:
    """
    Return the newest stock_pitch for the given base ticker (e.g. CSU for CSU.TO)
    with date_original within the last ``days`` days, or None.
    """
    base = ticker_base.strip().upper()
    if not base:
        return None
    root = (os.getenv("YELLOWBRICK_SUPABASE_URL") or _DEFAULT_SUPABASE_URL).rstrip("/")
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    url = f"{root}/rest/v1/stock_pitch"
    params = {
        "select": ",".join(
            [
                "title",
                "summary_short",
                "summary_paragraph",
                "url",
                "date_original",
                "given_ticker",
            ]
        ),
        "given_ticker": f"eq.{base}",
        "date_original": f"gte.{cutoff}",
        "order": "date_original.desc",
        "limit": "1",
    }
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, params=params, headers=_rest_headers())
        response.raise_for_status()
        rows = response.json()
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    return row if isinstance(row, dict) else None
