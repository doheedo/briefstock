from pathlib import Path


def test_oracle_timer_runs_at_1900_kst() -> None:
    timer = Path("deploy/oracle/daily-stock-briefing.timer").read_text(
        encoding="utf-8"
    )

    assert "Run Daily Stock Briefing at 19:00 KST" in timer
    assert "OnCalendar=*-*-* 19:00:00 Asia/Seoul" in timer
