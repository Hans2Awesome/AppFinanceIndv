"""Resolve the real client IP when the API runs behind a reverse proxy.

The backend is served through Cloudflare Tunnel, so the TCP peer of every
request is localhost. Reading ``request.client.host`` directly would make the
login limiter treat every user as the same client and lock out the whole app
after five bad passwords.

Forwarded headers are only trusted when the peer itself is a trusted proxy,
which keeps a directly connected client from spoofing its address. Override the
list with ``TRUSTED_PROXIES`` (comma separated) when the proxy address differs.
"""

from __future__ import annotations

import os

from fastapi import Request

_DEFAULT_TRUSTED_PROXIES = frozenset(
    {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"}
)

# Cloudflare sets CF-Connecting-IP to the original client. X-Forwarded-For is
# the generic fallback and is read left to right; the first entry is the client.
_FORWARDED_HEADERS = ("CF-Connecting-IP", "X-Forwarded-For")


def trusted_proxies() -> frozenset[str]:
    """Return the configured proxy addresses, defaulting to localhost."""

    raw = os.getenv("TRUSTED_PROXIES", "").strip()
    if not raw:
        return _DEFAULT_TRUSTED_PROXIES
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def client_ip(request: Request) -> str:
    """Return the client address, honoring proxy headers from trusted peers."""

    peer = request.client.host if request.client else "unknown"
    if peer not in trusted_proxies():
        return peer

    for header in _FORWARDED_HEADERS:
        value = request.headers.get(header)
        if not value:
            continue
        candidate = value.split(",")[0].strip()
        if candidate:
            return candidate

    return peer