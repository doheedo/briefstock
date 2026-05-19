from __future__ import annotations

from press_release_collector.core.models import PressRelease
from press_release_collector.core.normalize import normalize_title


def dedupe_press_releases(releases: list[PressRelease]) -> list[PressRelease]:
    seen_uids: set[str] = set()
    seen_title_keys: set[tuple[str, str]] = set()
    out: list[PressRelease] = []
    for release in releases:
        title_key = (release.ticker.upper(), normalize_title(release.title))
        if release.uid and release.uid in seen_uids:
            continue
        if title_key in seen_title_keys:
            continue
        if release.uid:
            seen_uids.add(release.uid)
        seen_title_keys.add(title_key)
        out.append(release)
    return out
