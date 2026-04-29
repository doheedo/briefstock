from pathlib import Path

from daily_stock_briefing.domain.models import WagnHoldingItem
from daily_stock_briefing.services import wagn_holdings_enrichment as svc


def test_build_wagn_holdings_section_detects_weight_changes(tmp_path, monkeypatch) -> None:
    snapshot_dir = Path(tmp_path)

    def _first_fetch():
        return "04/27/2026", [
            WagnHoldingItem(ticker="AAA", name="A Co", weight_pct=10.0),
            WagnHoldingItem(ticker="BBB", name="B Co", weight_pct=9.0),
        ]

    monkeypatch.setattr(svc, "fetch_wagn_holdings_csv", _first_fetch)
    first = svc.build_wagn_holdings_section("2026-04-29", snapshot_dir=snapshot_dir)
    assert first.total_holdings == 2
    assert first.notable_changes
    assert any(change.change_type == "added" for change in first.notable_changes)

    def _second_fetch():
        return "04/28/2026", [
            WagnHoldingItem(ticker="AAA", name="A Co", weight_pct=12.5),
            WagnHoldingItem(ticker="CCC", name="C Co", weight_pct=4.2),
        ]

    monkeypatch.setattr(svc, "fetch_wagn_holdings_csv", _second_fetch)
    second = svc.build_wagn_holdings_section("2026-04-30", snapshot_dir=snapshot_dir)
    kinds = {change.change_type for change in second.notable_changes}
    assert "weight_changed" in kinds
    assert "added" in kinds
    assert "removed" in kinds
