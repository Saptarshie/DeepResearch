from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


def is_safe_url(url: str) -> bool:
    """Return True if the URL is safe to fetch.

    http/https only, no private/loopback/reserved/multicast/CGNAT IPs.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    hostname = hostname.rstrip(".")
    if not hostname:
        return False
    if hostname.lower() in _BLOCKED_HOSTS:
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_multicast:
            return False
        # CGNAT range (RFC 6598) is not classified as private by ipaddress
        if ip in _CGNAT_NETWORK:
            return False
    except ValueError:
        pass
    return True
