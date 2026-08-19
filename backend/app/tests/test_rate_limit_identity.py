"""Regression test for a real rate-limiting bug (Technical Review #15):
get_remote_address() alone returns the reverse proxy's own address for every
request behind Render/Vercel/any load balancer, so the entire public
deployment shared one rate-limit bucket instead of each visitor getting
their own. client_identity() fixes this by reading X-Forwarded-For, trusted
only TRUSTED_PROXY_HOPS positions from the end (the client's own end of that
header is attacker-controlled)."""
from unittest.mock import MagicMock

from app.core.config import settings
from app.core.rate_limit import client_identity


def _request(xff: str | None, remote_addr: str = "10.0.0.1"):
    req = MagicMock()
    req.headers = {"x-forwarded-for": xff} if xff is not None else {}
    req.client = MagicMock(host=remote_addr)
    return req


def test_client_identity_uses_trusted_hop_from_xff(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    # Client-controlled prefix, then the one hop actually appended by the proxy.
    req = _request("203.0.113.5, 198.51.100.9")
    assert client_identity(req) == "ip:198.51.100.9"


def test_client_identity_ignores_client_controlled_prefix(monkeypatch):
    """A client can prepend arbitrary fake hops to XFF -- only the entry the
    trusted proxy itself appended (TRUSTED_PROXY_HOPS from the end) may be trusted."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    honest = client_identity(_request("198.51.100.9"))
    spoofed = client_identity(_request("1.2.3.4, 198.51.100.9"))
    assert honest == spoofed == "ip:198.51.100.9"


def test_client_identity_falls_back_to_remote_address_without_xff(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    req = _request(None)
    assert client_identity(req) == "ip:10.0.0.1"


def test_client_identity_ignores_xff_when_zero_hops_trusted(monkeypatch):
    """TRUSTED_PROXY_HOPS=0 means "no proxy in front, don't trust XFF at all" --
    must fall back to the raw socket address, not misread an empty/short header."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    req = _request("203.0.113.5")
    assert client_identity(req) == "ip:10.0.0.1"
