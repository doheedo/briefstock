from pathlib import Path


def test_oracle_timer_runs_at_2230_kst() -> None:
    timer = Path("deploy/oracle/daily-stock-briefing.timer").read_text(
        encoding="utf-8"
    )

    assert "Run Daily Stock Briefing at 22:30 KST" in timer
    assert "OnCalendar=*-*-* 22:30:00 Asia/Seoul" in timer
