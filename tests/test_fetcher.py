from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deepresearch.fetcher import FetchResult, PageFetcher


@pytest.fixture
async def fetcher() -> AsyncGenerator[PageFetcher, None]:
    f = PageFetcher(timeout=5.0, max_retries=1)
    yield f
    await f.close()


async def test_fetch_http_success(fetcher: PageFetcher) -> None:
    mock_response = MagicMock()
    mock_response.url = "http://example.com"
    mock_response.status_code = 200
    mock_response.text = "<html><body>Hello World</body></html>"
    mock_response.headers = {"content-type": "text/html"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetcher.fetch_http("http://example.com")
        assert result.status_code == 200
        assert "Hello World" in result.html


async def test_fetcher_close_releases_resources(fetcher: PageFetcher) -> None:
    # Trigger client creation
    _ = await fetcher._get_http_client()
    assert fetcher._http_client is not None
    await fetcher.close()
    assert fetcher._http_client is None


async def test_fetch_browser_fallback_on_short_html(fetcher: PageFetcher) -> None:
    with patch.object(fetcher, "fetch_http", new_callable=AsyncMock) as mock_http, \
         patch.object(fetcher, "fetch_browser", new_callable=AsyncMock) as mock_browser:
        mock_http.return_value = FetchResult(
            url="http://example.com",
            final_url="http://example.com",
            status_code=200,
            html="<html></html>",
            fetch_mode="http",
        )
        mock_browser.return_value = FetchResult(
            url="http://example.com",
            final_url="http://example.com",
            status_code=200,
            html="<html><body>Full content</body></html>",
            fetch_mode="browser",
        )
        result = await fetcher.fetch("http://example.com")
        mock_http.assert_awaited_once()
        mock_browser.assert_awaited_once()
        assert result.fetch_mode == "browser"


async def test_fetcher_close_with_browser(fetcher: PageFetcher) -> None:
    # Mock browser and playwright
    mock_browser = AsyncMock()
    mock_playwright = AsyncMock()
    fetcher._browser = mock_browser
    fetcher._playwright = mock_playwright
    # Trigger http client creation
    _ = await fetcher._get_http_client()
    await fetcher.close()
    assert fetcher._http_client is None
    assert fetcher._browser is None
    assert fetcher._playwright is None
    mock_browser.close.assert_awaited_once()
    mock_playwright.stop.assert_awaited_once()
