"""Health / reachability probes — shared by `status` and `up`-gating.

Honest by construction (Principle I): a probe answers "is this reachable RIGHT
NOW", never "should it be up". Unreachable → False, never an assumption.
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse

import httpx

from .models import Service


def reachable(service: Service, timeout: float = 2.0) -> bool:
    """True iff the service answers right now (http 2xx-4xx, or a tcp connect)."""
    kind = service.health.type if service.health else "tcp"
    if kind == "http":
        return _http_ok(service, timeout)
    return _tcp_ok(service, timeout)


def _http_ok(service: Service, timeout: float) -> bool:
    base = service.url.rstrip("/")
    path = service.health.path if (service.health and service.health.path) else "/"
    try:
        # <500 = the service answered (even 404 means it's up); >=500 / network error = down
        return httpx.get(base + path, timeout=timeout).status_code < 500
    except Exception:  # noqa: BLE001 - any failure means "not reachable"
        return False


def _tcp_ok(service: Service, timeout: float) -> bool:
    host, port = _host_port(service)
    if not host or not port:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _host_port(service: Service) -> tuple[str | None, int | None]:
    parsed = urlparse(service.url)
    host = parsed.hostname or "127.0.0.1"
    return host, (service.port or parsed.port)
