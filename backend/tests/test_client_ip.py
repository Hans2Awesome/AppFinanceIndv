"""Client IP resolution behind the Cloudflare Tunnel reverse proxy."""

from __future__ import annotations

from starlette.requests import Request

from backend.app.auth.client_ip import client_ip


def make_request(headers: dict[str, str] | None = None, client=("127.0.0.1", 1234)):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (name.lower().encode(), value.encode())
            for name, value in (headers or {}).items()
        ],
    }
    if client is not None:
        scope["client"] = client
    return Request(scope)


def test_cloudflare_header_is_used_for_trusted_peer() -> None:
    request = make_request({"CF-Connecting-IP": "203.0.113.7"})
    assert client_ip(request) == "203.0.113.7"


def test_forwarded_for_uses_the_first_hop() -> None:
    request = make_request({"X-Forwarded-For": "198.51.100.4, 10.0.0.2"})
    assert client_ip(request) == "198.51.100.4"


def test_cloudflare_header_wins_over_forwarded_for() -> None:
    request = make_request(
        {
            "CF-Connecting-IP": "203.0.113.7",
            "X-Forwarded-For": "198.51.100.4",
        }
    )
    assert client_ip(request) == "203.0.113.7"


def test_untrusted_peer_cannot_spoof_forwarded_header() -> None:
    request = make_request(
        {"CF-Connecting-IP": "203.0.113.7"},
        client=("192.0.2.50", 4321),
    )
    assert client_ip(request) == "192.0.2.50"


def test_peer_without_forwarded_header_is_returned() -> None:
    assert client_ip(make_request()) == "127.0.0.1"


def test_missing_client_is_unknown() -> None:
    assert client_ip(make_request(client=None)) == "unknown"


def test_trusted_proxies_can_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.5")
    request = make_request(
        {"CF-Connecting-IP": "203.0.113.7"},
        client=("10.0.0.5", 5555),
    )
    assert client_ip(request) == "203.0.113.7"

    localhost = make_request({"CF-Connecting-IP": "203.0.113.7"})
    assert client_ip(localhost) == "127.0.0.1"