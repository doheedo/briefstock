from __future__ import annotations

import sqlite3
from pathlib import Path

from press_release_collector.core.models import PressRelease


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS press_releases (
                uid TEXT PRIMARY KEY,
                ticker TEXT,
                company_name TEXT,
                title TEXT,
                url TEXT,
                published_at TEXT,
                source_name TEXT,
                source_type TEXT,
                summary TEXT,
                content TEXT,
                collected_at TEXT
            )
            """
        )


def upsert_press_release(db_path: Path, release: PressRelease) -> bool:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        before = conn.total_changes
        conn.execute(
            """
            INSERT INTO press_releases (
                uid, ticker, company_name, title, url, published_at,
                source_name, source_type, summary, content, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                ticker=excluded.ticker,
                company_name=excluded.company_name,
                title=excluded.title,
                url=excluded.url,
                published_at=excluded.published_at,
                source_name=excluded.source_name,
                source_type=excluded.source_type,
                summary=excluded.summary,
                content=excluded.content,
                collected_at=excluded.collected_at
            """,
            (
                release.uid,
                release.ticker,
                release.company_name,
                release.title,
                release.url,
                release.published_at,
                release.source_name,
                release.source_type,
                release.summary,
                release.content,
                release.collected_at,
            ),
        )
        return conn.total_changes > before and _was_new_insert(conn, release.uid)


def _was_new_insert(conn: sqlite3.Connection, uid: str) -> bool:
    row = conn.execute(
        "SELECT changes(), COUNT(*) FROM press_releases WHERE uid = ?",
        (uid,),
    ).fetchone()
    return bool(row and row[0] == 1 and row[1] == 1)


def bulk_upsert_press_releases(db_path: Path, releases: list[PressRelease]) -> int:
    inserted = 0
    for release in releases:
        if not _exists(db_path, release.uid):
            inserted += 1
        upsert_press_release(db_path, release)
    return inserted


def _exists(db_path: Path, uid: str) -> bool:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM press_releases WHERE uid = ?",
            (uid,),
        ).fetchone()
    return row is not None


def get_recent_press_releases(
    db_path: Path,
    ticker: str,
    limit: int = 20,
) -> list[PressRelease]:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT uid, ticker, company_name, title, url, published_at,
                   source_name, source_type, summary, content, collected_at
            FROM press_releases
            WHERE ticker = ?
            ORDER BY COALESCE(published_at, collected_at) DESC
            LIMIT ?
            """,
            (ticker.upper(), limit),
        ).fetchall()
    return [
        PressRelease(
            uid=row[0],
            ticker=row[1],
            company_name=row[2],
            title=row[3],
            url=row[4],
            published_at=row[5],
            source_name=row[6],
            source_type=row[7],
            summary=row[8],
            content=row[9],
            collected_at=row[10],
        )
        for row in rows
    ]
