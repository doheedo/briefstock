from __future__ import annotations

import json
from pathlib import Path

from daily_stock_briefing.adapters.wagn.filepoint_holdings import (
    WAGN_HOLDINGS_CSV_URL,
    WAGN_SOURCE_URL,
    fetch_wagn_holdings_csv,
)
from daily_stock_briefing.domain.models import (
    WagnHoldingChange,
    WagnHoldingItem,
    WagnHoldingsSection,
)


def _key(item: WagnHoldingItem) -> str:
    return item.ticker.strip().upper()


def _to_item(payload: dict) -> WagnHoldingItem | None:
    try:
        return WagnHoldingItem(
            ticker=str(payload["ticker"]),
            name=str(payload["name"]),
            weight_pct=float(payload["weight_pct"]),
        )
    except Exception:
        return None


def _load_previous(snapshot_path: Path) -> list[WagnHoldingItem]:
    if not snapshot_path.exists():
        return []
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = []
    for raw in payload.get("holdings", []):
        if isinstance(raw, dict):
            item = _to_item(raw)
            if item is not None:
                items.append(item)
    return items


def _build_changes(
    previous: list[WagnHoldingItem],
    current: list[WagnHoldingItem],
) -> list[WagnHoldingChange]:
    previous_map = {_key(item): item for item in previous}
    current_map = {_key(item): item for item in current}

    out: list[WagnHoldingChange] = []
    for ticker, item in current_map.items():
        prev = previous_map.get(ticker)
        if prev is None:
            out.append(
                WagnHoldingChange(
                    ticker=item.ticker,
                    name=item.name,
                    previous_weight_pct=None,
                    current_weight_pct=item.weight_pct,
                    delta_pct=None,
                    change_type="added",
                )
            )
            continue
        delta = item.weight_pct - prev.weight_pct
        if abs(delta) >= 0.1:
            out.append(
                WagnHoldingChange(
                    ticker=item.ticker,
                    name=item.name,
                    previous_weight_pct=prev.weight_pct,
                    current_weight_pct=item.weight_pct,
                    delta_pct=delta,
                    change_type="weight_changed",
                )
            )

    for ticker, item in previous_map.items():
        if ticker not in current_map:
            out.append(
                WagnHoldingChange(
                    ticker=item.ticker,
                    name=item.name,
                    previous_weight_pct=item.weight_pct,
                    current_weight_pct=None,
                    delta_pct=None,
                    change_type="removed",
                )
            )
    out.sort(key=lambda c: abs(c.delta_pct or 0.0), reverse=True)
    return out[:12]


def _summary_ko(changes: list[WagnHoldingChange], as_of: str | None) -> str:
    date_part = f"(기준일 {as_of}) " if as_of else ""
    if not changes:
        return f"{date_part}직전 스냅샷 대비 유의미한 비중/종목 변화가 없습니다."
    added = sum(1 for c in changes if c.change_type == "added")
    removed = sum(1 for c in changes if c.change_type == "removed")
    reweighted = sum(1 for c in changes if c.change_type == "weight_changed")
    return (
        f"{date_part}직전 스냅샷 대비 비중 변화 {reweighted}건, 신규 편입 {added}건, 제외 {removed}건을 감지했습니다."
    )


def _save_snapshot(
    run_date: str,
    as_of_date: str | None,
    holdings: list[WagnHoldingItem],
    *,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_date": run_date,
        "as_of_date": as_of_date,
        "source_url": WAGN_SOURCE_URL,
        "download_url": WAGN_HOLDINGS_CSV_URL,
        "holdings": [item.model_dump() for item in holdings],
    }
    (output_dir / f"{run_date}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_wagn_holdings_section(
    run_date: str,
    *,
    snapshot_dir: Path = Path("reports/wagn"),
) -> WagnHoldingsSection:
    previous = _load_previous(snapshot_dir / "latest.json")
    try:
        as_of, current = fetch_wagn_holdings_csv()
    except Exception as exc:
        return WagnHoldingsSection(
            source_url=WAGN_SOURCE_URL,
            download_url=WAGN_HOLDINGS_CSV_URL,
            summary_ko="WAGN holdings 조회에 실패했습니다.",
            error=str(exc),
        )
    changes = _build_changes(previous, current)
    section = WagnHoldingsSection(
        as_of_date=as_of,
        source_url=WAGN_SOURCE_URL,
        download_url=WAGN_HOLDINGS_CSV_URL,
        total_holdings=len(current),
        top_holdings=current[:10],
        notable_changes=changes,
        summary_ko=_summary_ko(changes, as_of),
    )
    _save_snapshot(run_date, as_of, current, output_dir=snapshot_dir)
    return section
