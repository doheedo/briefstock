from datetime import UTC, datetime

from press_release_collector.core.dedupe import dedupe_press_releases
from press_release_collector.core.models import PressRelease
from press_release_collector.core.normalize import normalize_press_release, normalize_title
from press_release_collector.core.storage import (
    bulk_upsert_press_releases,
    get_recent_press_releases,
    init_db,
)


def _release(**kwargs) -> PressRelease:
    payload = {
        "ticker": "csu.to",
        "company_name": " Constellation Software ",
        "title": "  CONSTELLATION   Announces   Results ",
        "url": "https://example.com/release?utm_source=x",
        "published_at": "2026-05-08T10:00:00+00:00",
        "source_name": "CSU",
        "source_type": "official_html",
        "summary": " Revenue increased. ",
        "content": " Revenue increased.  Cash flow improved. ",
    }
    payload.update(kwargs)
    return PressRelease.from_raw(**payload)


def test_press_release_uid_is_stable_after_normalization() -> None:
    first = normalize_press_release(_release())
    second = normalize_press_release(
        _release(
            title="constellation announces results",
            url="https://example.com/release",
        )
    )

    assert first.uid == second.uid
    assert first.ticker == "CSU.TO"
    assert first.company_name == "Constellation Software"
    assert first.published_at == "2026-05-08T10:00:00+00:00"


def test_normalize_title_collapses_space_and_case() -> None:
    assert normalize_title("  CONSTELLATION   Announces   Results ") == (
        "constellation announces results"
    )


def test_dedupe_removes_same_ticker_and_normalized_title() -> None:
    releases = [
        normalize_press_release(_release(url="https://example.com/a")),
        normalize_press_release(_release(url="https://example.com/b")),
        normalize_press_release(_release(title="Different update")),
    ]

    out = dedupe_press_releases(releases)

    assert [item.title for item in out] == [
        "CONSTELLATION Announces Results",
        "Different update",
    ]


def test_sqlite_storage_upserts_and_returns_recent(tmp_path) -> None:
    db_path = tmp_path / "press_releases.sqlite"
    init_db(db_path)
    first = normalize_press_release(_release(summary="old"))
    updated = first.model_copy(
        update={
            "summary": "new",
            "collected_at": datetime(2026, 5, 8, tzinfo=UTC).isoformat(),
        }
    )

    assert bulk_upsert_press_releases(db_path, [first]) == 1
    assert bulk_upsert_press_releases(db_path, [updated]) == 0
    rows = get_recent_press_releases(db_path, "CSU.TO", limit=5)

    assert len(rows) == 1
    assert rows[0].summary == "new"
