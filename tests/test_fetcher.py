from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from deepresearch.fetcher import PageFetcher, FetchResult


@pytest.fixture
async def fetcher():
    f = PageFetcher(timeout=5.0, max_retries=1)
    yield f
    await f.close()


async def test_fetch_http_success(fetcher) -> None:
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


async def test_fetcher_close_releases_resources(fetcher) -> None:
    await fetcher.close()
    assert fetcher._http_client is None
