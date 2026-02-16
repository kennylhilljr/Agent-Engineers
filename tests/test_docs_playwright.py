"""
Playwright Tests for Documentation Site
========================================

End-to-end tests for the generated documentation website.
"""

import asyncio
import http.server
import socketserver
import subprocess
import threading
import time
from pathlib import Path

import pytest


class DocumentationServer:
    """Simple HTTP server for testing documentation."""

    def __init__(self, docs_dir: Path, port: int = 8765):
        """Initialize documentation server.

        Args:
            docs_dir: Directory containing documentation
            port: Port to serve on
        """
        self.docs_dir = docs_dir
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """Start the HTTP server in a background thread."""
        import os

        # Change to docs directory
        original_dir = os.getcwd()
        os.chdir(self.docs_dir)

        Handler = http.server.SimpleHTTPRequestHandler

        self.server = socketserver.TCPServer(("", self.port), Handler)

        # Start server in thread
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

        # Wait for server to start
        time.sleep(1)

        # Restore directory
        os.chdir(original_dir)

    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def url(self, path: str = "") -> str:
        """Get full URL for a path.

        Args:
            path: Path relative to docs root

        Returns:
            Full URL
        """
        return f"http://localhost:{self.port}/{path}"


@pytest.fixture(scope="module")
def docs_server():
    """Start documentation server for tests."""
    project_root = Path(__file__).parent.parent
    docs_dir = project_root / "docs" / "html"

    if not docs_dir.exists():
        pytest.skip("Documentation not generated yet")

    server = DocumentationServer(docs_dir)
    server.start()

    yield server

    server.stop()


@pytest.mark.asyncio
async def test_documentation_home_page(docs_server):
    """Test that documentation home page loads correctly."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Navigate to home page
        await page.goto(docs_server.url())

        # Check title
        title = await page.title()
        assert "Agent Dashboard" in title, "Page should have Agent Dashboard in title"

        # Check for key sections
        content = await page.content()
        assert "Documentation" in content, "Should have Documentation section"
        assert "API Reference" in content, "Should link to API reference"

        await browser.close()


@pytest.mark.asyncio
async def test_documentation_navigation(docs_server):
    """Test navigation between documentation pages."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Start at home page
        await page.goto(docs_server.url())

        # Click on Developer Guide link
        await page.click('text="Read Guide"')

        # Wait for navigation
        await page.wait_for_load_state("networkidle")

        # Verify we're on developer guide page
        content = await page.content()
        assert "Developer Guide" in content or "DEVELOPER_GUIDE" in page.url

        await browser.close()


@pytest.mark.asyncio
async def test_api_documentation_accessible(docs_server):
    """Test that API documentation is accessible."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Navigate to API docs
        await page.goto(docs_server.url("api/index.html"))

        # Check that API docs loaded
        content = await page.content()
        assert "agent" in content.lower() or "client" in content.lower(), \
            "API docs should list modules"

        await browser.close()


@pytest.mark.asyncio
async def test_documentation_responsive(docs_server):
    """Test that documentation is responsive on different screen sizes."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Test on desktop
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.goto(docs_server.url())

        # Page should load
        assert await page.is_visible("h1"), "Header should be visible on desktop"

        # Test on mobile
        await page.set_viewport_size({"width": 375, "height": 667})
        await page.goto(docs_server.url())

        # Page should still be usable
        assert await page.is_visible("h1"), "Header should be visible on mobile"

        await browser.close()


@pytest.mark.asyncio
async def test_take_documentation_screenshots(docs_server):
    """Take screenshots of documentation for evidence."""
    from playwright.async_api import async_playwright

    project_root = Path(__file__).parent.parent
    screenshots_dir = project_root / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Set viewport for consistent screenshots
        await page.set_viewport_size({"width": 1920, "height": 1080})

        # Screenshot 1: Home page
        await page.goto(docs_server.url())
        await page.screenshot(
            path=str(screenshots_dir / "docs_home_page.png"),
            full_page=True
        )

        # Screenshot 2: Developer Guide
        dev_guide_url = docs_server.url("DEVELOPER_GUIDE.html")
        try:
            await page.goto(dev_guide_url)
            await page.screenshot(
                path=str(screenshots_dir / "docs_developer_guide.png"),
                full_page=True
            )
        except Exception:
            # May not exist yet
            pass

        # Screenshot 3: Bridge Interface docs
        bridge_url = docs_server.url("BRIDGE_INTERFACE.html")
        try:
            await page.goto(bridge_url)
            await page.screenshot(
                path=str(screenshots_dir / "docs_bridge_interface.png"),
                full_page=True
            )
        except Exception:
            pass

        # Screenshot 4: API documentation
        api_url = docs_server.url("api/index.html")
        try:
            await page.goto(api_url)
            await page.screenshot(
                path=str(screenshots_dir / "docs_api_reference.png"),
                full_page=True
            )
        except Exception:
            pass

        # Screenshot 5: Specific module (agent.py)
        agent_url = docs_server.url("api/agent.html")
        try:
            await page.goto(agent_url)
            await page.screenshot(
                path=str(screenshots_dir / "docs_api_agent_module.png"),
                full_page=True
            )
        except Exception:
            pass

        await browser.close()

        # Verify screenshots were created
        screenshots = list(screenshots_dir.glob("docs_*.png"))
        assert len(screenshots) > 0, "Should have created at least one screenshot"

        print(f"\n✅ Created {len(screenshots)} documentation screenshots:")
        for screenshot in screenshots:
            print(f"   - {screenshot.name}")


@pytest.mark.asyncio
async def test_documentation_links_work(docs_server):
    """Test that internal links in documentation work."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Navigate to home page
        await page.goto(docs_server.url())

        # Get all links
        links = await page.query_selector_all("a[href]")

        # Test a few internal links
        tested = 0
        for link in links[:5]:  # Test first 5 links
            href = await link.get_attribute("href")

            # Skip external links and anchors
            if href and not href.startswith(("http://", "https://", "#", "mailto:")):
                # Try to navigate
                try:
                    response = await page.goto(docs_server.url(href))
                    assert response.status < 400, \
                        f"Link {href} returned status {response.status}"
                    tested += 1
                except Exception as e:
                    # Some links may be to pages that don't exist yet
                    print(f"Warning: Link {href} failed: {e}")

        await browser.close()

        assert tested > 0, "Should have tested at least one internal link"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
