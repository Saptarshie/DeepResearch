from __future__ import annotations
import pytest
import respx
from httpx import Response
from deepresearch.searx_client import SearxClient


@pytest.fixture
def searx_client(config) -> SearxClient:
    return SearxClient(config.searxng_base_url)


@respx.mock
async def test_search_returns_results(searx_client) -> None:
    route = respx.get("http://localhost:8080/search").mock(
        return_value=Response(
            200,
            json={
                "results": [
                    {
                        "title": "Test Title",
                        "url": "http://example.com",
                        "content": "Test snippet",
                        "engines": ["google"],
                    }
                ]
            },
        )
    )
    results = await searx_client.search("test query")
    assert len(results) == 1
    assert results[0].title == "Test Title"
    assert results[0].url == "http://example.com"
    assert route.called


async def test_close_client() -> None:
    client = SearxClient("http://localhost:8080")
    await client.close()
