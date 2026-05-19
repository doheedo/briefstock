from __future__ import annotations

import logging

from press_release_collector.core.models import PressRelease

logger = logging.getLogger(__name__)


def collect_wire(
    ticker: str,
    company_name: str,
    wire_queries: list[str],
) -> list[PressRelease]:
    # MVP fallback hook. Wire services often block HTML scraping and each has
    # different search/RSS constraints, so keep the interface stable without
    # making brittle network calls in the first implementation.
    if wire_queries:
        logger.info("Wire press release collection not enabled for %s", ticker)
    return []
