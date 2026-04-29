from __future__ import annotations
import pytest
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
