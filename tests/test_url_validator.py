from __future__ import annotations

from deepresearch.url_validator import is_safe_url


def test_public_http_url_is_safe() -> None:
    assert is_safe_url("http://example.com") is True


def test_https_url_is_safe() -> None:
    assert is_safe_url("https://example.com/path") is True


def test_localhost_is_blocked() -> None:
    assert is_safe_url("http://localhost:8080") is False


def test_private_ip_is_blocked() -> None:
    assert is_safe_url("http://192.168.1.1") is False


def test_file_scheme_is_blocked() -> None:
    assert is_safe_url("file:///etc/passwd") is False


def test_empty_hostname_is_blocked() -> None:
    assert is_safe_url("http://") is False
    assert is_safe_url("http:///path") is False


def test_ipv6_loopback_is_blocked() -> None:
    assert is_safe_url("http://[::1]") is False


def test_zero_ip_is_blocked() -> None:
    assert is_safe_url("http://0.0.0.0") is False


def test_cgnat_is_blocked() -> None:
    assert is_safe_url("http://100.64.0.1") is False


def test_trailing_dot_localhost_is_blocked() -> None:
    assert is_safe_url("http://localhost.") is False
    assert is_safe_url("http://127.0.0.1.") is False


def test_uppercase_scheme_is_allowed() -> None:
    assert is_safe_url("HTTP://example.com") is True
