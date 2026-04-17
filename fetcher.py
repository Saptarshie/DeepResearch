from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Optional
import httpx
from playwright.async_api import async_playwright
@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    html: str
    fetch_mode: str
    content_type: str = ""
class PageFetcher:
    def __init__(self, timeout: float = 20.0, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
    async def fetch_http(self, url: str, attempt: int = 1) -> FetchResult:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; DeepResearchBot/1.0)"}
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
    async def fetch_browser(self, url: str, wait_ms: int = 2000) -> FetchResult:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            response = await page.goto(
                url, wait_until="networkidle", timeout=int(self.timeout * 1000)
            )
            await page.wait_for_timeout(wait_ms)
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
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if force_browser:
                    return await self.fetch_browser(url)
                res = await self.fetch_http(url, attempt)
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