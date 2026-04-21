"""Web fetcher — moved from deepresearch/fetcher.py, enhanced."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
import httpx


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    html: str
    fetch_mode: str
    content_type: str = ""


class WebFetcher:
    """Adaptive page fetcher: fast HTTP first, browser fallback for JS-heavy sites."""

    def __init__(self, timeout: float = 20.0, max_retries: int = 3, browser_wait_ms: int = 2000):
        self.timeout = timeout
        self.max_retries = max_retries
        self.browser_wait_ms = browser_wait_ms

    async def fetch_http(self, url: str) -> FetchResult:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; OmegaResearchBot/1.0)"}
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.timeout, headers=headers
        ) as client:
            r = await client.get(url)
            return FetchResult(
                url=url,
                final_url=str(r.url),
                status_code=r.status_code,
                html=r.text,
                fetch_mode="http",
                content_type=r.headers.get("content-type", ""),
            )

    async def fetch_browser(self, url: str) -> FetchResult:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            response = await page.goto(
                url, wait_until="networkidle", timeout=int(self.timeout * 1000)
            )
            await page.wait_for_timeout(self.browser_wait_ms)
            html = await page.content()
            final_url = page.url
            status_code = response.status if response else 0
            await browser.close()
            return FetchResult(
                url=url,
                final_url=final_url,
                status_code=status_code,
                html=html,
                fetch_mode="browser",
                content_type="text/html",
            )

    async def fetch(self, url: str, force_browser: bool = False) -> FetchResult:
        """Fetch with retry + fallback logic."""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if force_browser:
                    return await self.fetch_browser(url)

                res = await self.fetch_http(url)
                if len(res.html.strip()) < 500:
                    return await self.fetch_browser(url)
                return res

            except (httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                if not force_browser:
                    try:
                        return await self.fetch_browser(url)
                    except Exception:
                        pass
                raise
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                raise
        raise last_error or Exception("Fetch failed after retries")
