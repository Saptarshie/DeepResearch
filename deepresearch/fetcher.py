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

    @staticmethod
    def _sync_fetch_browser(
        url: str, timeout: float, browser_wait_ms: int
    ) -> FetchResult:
        """Sync Playwright fetch — safe to run inside run_in_executor."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                response = page.goto(
                    url, wait_until="networkidle", timeout=int(timeout * 1000)
                )
                page.wait_for_timeout(browser_wait_ms)
                html = page.content()
                final_url = page.url
                status_code = response.status if response else 0
            finally:
                page.close()
                browser.close()
        return FetchResult(
            url=url,
            final_url=final_url,
            status_code=status_code,
            html=html,
            fetch_mode="browser",
            content_type="text/html",
        )

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
        """Use sync Playwright in executor to avoid asyncio subprocess issues on Windows."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_fetch_browser, url, self.timeout, self.browser_wait_ms
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
                url=url,
                final_url=str(r.url),
                status_code=r.status_code,
                html="",
                fetch_mode="pdf",
                content_type=content_type,
            )
        return FetchResult(
            url=url,
            final_url=str(r.url),
            status_code=r.status_code,
            html=text,
            fetch_mode="pdf",
            content_type=content_type,
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
        if self._http_client is not None:
            with contextlib.suppress(Exception):
                await self._http_client.aclose()
            self._http_client = None
