from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from httpx import Limits

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    html: str
    fetch_mode: str
    content_type: str = ""


class PageFetcher:
    def __init__(
        self,
        timeout: float = 20.0,
        max_retries: int = 3,
        browser_wait_ms: int = 2000,
        enable_browser: bool = True,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.browser_wait_ms = browser_wait_ms
        self.enable_browser = enable_browser
        self._http_client: httpx.AsyncClient | None = None
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._page: Any | None = None
        self._limits = Limits(max_connections=100, max_keepalive_connections=20)

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0 (compatible; DeepResearchBot/1.0)"},
                limits=self._limits,
            )
        return self._http_client

    async def _get_browser(self) -> Any:
        if self._browser is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def fetch_http(self, url: str) -> FetchResult:
        client = await self._get_http_client()
        r = await client.get(url)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "application/pdf" in content_type.lower():
            return FetchResult(
                url=url,
                final_url=str(r.url),
                status_code=r.status_code,
                html="",
                fetch_mode="http",
                content_type=content_type,
            )
        return FetchResult(
            url=url,
            final_url=str(r.url),
            status_code=r.status_code,
            html=r.text,
            fetch_mode="http",
            content_type=content_type,
        )

    async def fetch_browser(self, url: str) -> FetchResult:
        browser = await self._get_browser()
        if self._page is None or getattr(self._page, "is_closed", lambda: True)():
            self._page = await browser.new_page()
        page = self._page
        try:
            response = await page.goto(
                url, wait_until="networkidle", timeout=int(self.timeout * 1000)
            )
            await page.wait_for_timeout(self.browser_wait_ms)
            html = await page.content()
            final_url = page.url
            status_code = response.status if response else 0
        except Exception:
            self._page = None
            raise
        return FetchResult(
            url=url,
            final_url=final_url,
            status_code=status_code,
            html=html,
            fetch_mode="browser",
            content_type="text/html",
        )

    async def fetch_pdf(self, url: str, max_pages: int = 50) -> FetchResult:
        import fitz
        client = await self._get_http_client()
        r = await client.get(url)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        try:
            with fitz.open(stream=r.content, filetype="pdf") as doc:
                text_parts = []
                for i, page in enumerate(doc):
                    if i >= max_pages:
                        break
                    page_text = page.get_text()
                    if page_text.strip():
                        text_parts.append(page_text)
                text = "\n\n".join(text_parts)
        except Exception as e:
            logger.warning("PDF extraction failed for %s: %s", url, e)
            return FetchResult(
                url=url, final_url=str(r.url), status_code=r.status_code,
                html="", fetch_mode="pdf", content_type=content_type,
            )
        return FetchResult(
            url=url, final_url=str(r.url), status_code=r.status_code,
            html=text, fetch_mode="pdf", content_type=content_type,
        )

    async def fetch(self, url: str, force_browser: bool = False) -> FetchResult:
        for attempt in range(1, self.max_retries + 1):
            try:
                if force_browser and self.enable_browser:
                    return await self.fetch_browser(url)
                res = await self.fetch_http(url)
                if "application/pdf" in res.content_type.lower() or url.lower().endswith(".pdf"):
                    return await self.fetch_pdf(url)
                if len(res.html.strip()) < 500 and self.enable_browser:
                    return await self.fetch_browser(url)
                return res
            except asyncio.CancelledError:
                raise
            except Exception:
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                if not force_browser and self.enable_browser:
                    try:
                        return await self.fetch_browser(url)
                    except Exception:
                        pass
                raise
        raise RuntimeError("Unexpected end of fetch loop")

    async def close(self) -> None:
        if self._page is not None:
            with contextlib.suppress(Exception):
                await self._page.close()
            self._page = None
        if self._http_client is not None:
            with contextlib.suppress(Exception):
                await self._http_client.aclose()
            self._http_client = None
        if self._browser is not None:
            with contextlib.suppress(Exception):
                await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            with contextlib.suppress(Exception):
                await self._playwright.stop()
            self._playwright = None
