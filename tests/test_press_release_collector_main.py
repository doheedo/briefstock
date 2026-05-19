from pathlib import Path

from press_release_collector.core.models import PressRelease
from press_release_collector.core.storage import get_recent_press_releases
from press_release_collector.main import run


def test_run_loads_sources_and_stores_new_releases(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.yaml"
    db_path = tmp_path / "press.sqlite"
    config.write_text(
        """
companies:
  - ticker: CSU.TO
    company_name: Constellation Software
    official_sources:
      - type: html
        url: "https://www.csisoftware.com/category/press-releases/"
    wire_queries:
      - "Constellation Software"
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "press_release_collector.main.collect_html",
        lambda **kwargs: [
            PressRelease.from_raw(
                ticker="CSU.TO",
                company_name="Constellation Software",
                title="Constellation Announces Results for Q1",
                url="https://example.com/results",
                source_name="example.com",
                source_type="official_html",
                summary="Revenue increased.",
            )
        ],
    )
    monkeypatch.setattr("press_release_collector.main.collect_wire", lambda *args: [])

    counts = run(config, db_path)

    assert counts == {"CSU.TO": 1}
    rows = get_recent_press_releases(db_path, "CSU.TO")
    assert rows[0].title == "Constellation Announces Results for Q1"
