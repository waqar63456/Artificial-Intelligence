"""
Browser Automation Agent.
Uses Playwright to open the application in a browser and collect errors from
console logs, network requests, and JavaScript runtime errors.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from autodev.infrastructure.runtime_monitor import DetectedError, ErrorSeverity

logger = logging.getLogger("autodev")


@dataclass
class BrowserError:
    """Error detected in the browser."""

    message: str
    source: str  # "console", "network", "javascript", "page"
    severity: ErrorSeverity = ErrorSeverity.ERROR
    url: str = ""
    line_number: int = 0
    column_number: int = 0
    stack_trace: str = ""


@dataclass
class NetworkRequest:
    """A captured network request."""

    url: str
    method: str
    status: int = 0
    status_text: str = ""
    failed: bool = False
    error_text: str = ""
    duration_ms: float = 0.0


@dataclass
class BrowserTestResult:
    """Result of browser-based testing."""

    success: bool
    page_loaded: bool = False
    page_title: str = ""
    console_errors: list[BrowserError] = field(default_factory=list)
    network_errors: list[BrowserError] = field(default_factory=list)
    js_errors: list[BrowserError] = field(default_factory=list)
    failed_requests: list[NetworkRequest] = field(default_factory=list)
    screenshot_path: str = ""
    page_html: str = ""

    @property
    def all_errors(self) -> list[BrowserError]:
        return self.console_errors + self.network_errors + self.js_errors

    @property
    def error_count(self) -> int:
        return len(self.all_errors)

    def to_detected_errors(self) -> list[DetectedError]:
        """Convert browser errors to standard DetectedError format."""
        errors = []
        for be in self.all_errors:
            errors.append(DetectedError(
                message=be.message,
                severity=be.severity,
                source=f"browser:{be.source}",
                file_path="",
                line_number=be.line_number,
                column_number=be.column_number,
                stack_trace=be.stack_trace,
                raw_output=be.message,
            ))
        return errors


class BrowserAgent:
    """Automated browser testing using Playwright."""

    def __init__(self) -> None:
        self._browser: Any = None
        self._playwright: Any = None

    async def start(self) -> None:
        """Start the browser instance."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "playwright is required. Install with: pip install playwright && playwright install chromium"
            )

        logger.info("Starting browser automation...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        logger.info("Browser started successfully")

    async def stop(self) -> None:
        """Stop the browser instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser stopped")

    async def test_page(
        self,
        url: str,
        wait_seconds: float = 5.0,
        screenshot_path: str | None = None,
    ) -> BrowserTestResult:
        """
        Open a page and collect errors.

        Args:
            url: URL to test.
            wait_seconds: How long to wait for the page to settle.
            screenshot_path: Optional path to save a screenshot.

        Returns:
            BrowserTestResult with all detected issues.
        """
        if not self._browser:
            await self.start()

        logger.info("Testing page: %s", url)

        console_errors: list[BrowserError] = []
        network_errors: list[BrowserError] = []
        js_errors: list[BrowserError] = []
        failed_requests: list[NetworkRequest] = []

        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Set up console error listener
        def on_console(msg: Any) -> None:
            if msg.type in ("error", "warning"):
                console_errors.append(BrowserError(
                    message=msg.text,
                    source="console",
                    severity=ErrorSeverity.ERROR if msg.type == "error" else ErrorSeverity.WARNING,
                    url=url,
                ))

        page.on("console", on_console)

        # Set up page error listener (uncaught exceptions)
        def on_page_error(error: Any) -> None:
            js_errors.append(BrowserError(
                message=str(error),
                source="javascript",
                severity=ErrorSeverity.ERROR,
                url=url,
                stack_trace=str(error),
            ))

        page.on("pageerror", on_page_error)

        # Set up request failure listener
        def on_request_failed(request: Any) -> None:
            failed_requests.append(NetworkRequest(
                url=request.url,
                method=request.method,
                failed=True,
                error_text=request.failure or "Unknown failure",
            ))
            network_errors.append(BrowserError(
                message=f"Request failed: {request.method} {request.url}",
                source="network",
                severity=ErrorSeverity.ERROR,
                url=request.url,
            ))

        page.on("requestfailed", on_request_failed)

        # Navigate to the page
        page_loaded = False
        page_title = ""
        page_html = ""

        try:
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            page_loaded = response is not None and response.ok if response else False

            # Wait for the page to settle
            await asyncio.sleep(wait_seconds)

            page_title = await page.title()
            page_html = await page.content()

            # Check for HTTP errors
            if response and not response.ok:
                network_errors.append(BrowserError(
                    message=f"HTTP {response.status}: {response.status_text}",
                    source="network",
                    severity=ErrorSeverity.ERROR,
                    url=url,
                ))

            # Take screenshot if requested
            if screenshot_path:
                await page.screenshot(path=screenshot_path, full_page=True)
                logger.info("Screenshot saved: %s", screenshot_path)

        except Exception as e:
            logger.error("Browser navigation error: %s", str(e))
            js_errors.append(BrowserError(
                message=f"Navigation error: {str(e)}",
                source="page",
                severity=ErrorSeverity.CRITICAL,
                url=url,
            ))
        finally:
            await context.close()

        result = BrowserTestResult(
            success=page_loaded and len(console_errors) == 0 and len(js_errors) == 0,
            page_loaded=page_loaded,
            page_title=page_title,
            console_errors=console_errors,
            network_errors=network_errors,
            js_errors=js_errors,
            failed_requests=failed_requests,
            screenshot_path=screenshot_path or "",
            page_html=page_html[:5000],  # Limit HTML size
        )

        logger.info(
            "Browser test result: loaded=%s, errors=%d",
            page_loaded, result.error_count,
        )
        return result

    async def test_multiple_pages(
        self,
        urls: list[str],
        wait_seconds: float = 3.0,
    ) -> list[BrowserTestResult]:
        """
        Test multiple pages.

        Args:
            urls: List of URLs to test.
            wait_seconds: Wait time per page.

        Returns:
            List of BrowserTestResults.
        """
        results = []
        for url in urls:
            result = await self.test_page(url, wait_seconds)
            results.append(result)
        return results

    async def __aenter__(self) -> BrowserAgent:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()
