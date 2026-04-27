"""Shared URL normalization utilities.

Both the news adapter and the deduplication service need canonical URL
forms. This module is the single source of truth.
"""
from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str | None:
    """Return a canonical form of *url*, or ``None`` if it cannot be parsed.

    Normalization rules:
    - Scheme lowercased.
    - ``www.`` prefix stripped from the host.
    - Default ports (80 for http, 443 for https) omitted.
    - Trailing slashes stripped from the path.
    - Query string and fragment dropped.
    """
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname.lower() if parts.hostname else ""
        port = parts.port
    except ValueError:
        return None

    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    if port and not (
        (parts.scheme.lower() == "http" and port == 80)
        or (parts.scheme.lower() == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), host, path, "", ""))
