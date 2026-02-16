"""Playwright Browser Tests for Security Enforcement (AI-113).

Tests the security enforcement in the browser, verifying that the dashboard
UI correctly handles security checks for bash commands, file operations,
and MCP tool calls.
"""

import pytest
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser
from aiohttp import web
import tempfile
import subprocess
import time
import signal
import os

from dashboard.rest_api_server import RESTAPIServer


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def test_server():
    """Start test server for browser tests."""
    tmpdir = tempfile.mkdtemp()
    project_root = Path(tmpdir)

    server = RESTAPIServer(
        project_name="test-security",
        metrics_dir=project_root,
        port=8423,  # Use different port for tests
        host="127.0.0.1"
    )

    # Start server in background
    import threading
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server to start
    await asyncio.sleep(2)

    yield "http://127.0.0.1:8423"

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="module")
async def browser():
    """Create browser instance."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest.fixture
async def page(browser):
    """Create new page for each test."""
    page = await browser.new_page()
    yield page
    await page.close()


class TestSecurityBrowserUI:
    """Browser tests for security enforcement UI."""

    @pytest.mark.asyncio
    async def test_blocked_command_shows_error(self, page: Page, test_server: str):
        """Test Step 1: Blocked command shows error in UI."""
        # Navigate to dashboard
        await page.goto(test_server)

        # Make API call via browser fetch
        response = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/bash', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: 'sudo rm -rf /'})
                });
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        assert response['status'] == 403
        assert 'error' in response['data']

    @pytest.mark.asyncio
    async def test_forbidden_file_access_blocked(self, page: Page, test_server: str):
        """Test Step 2: Forbidden file access is blocked."""
        await page.goto(test_server)

        response = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/file/read', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({file_path: '/etc/passwd'})
                });
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        assert response['status'] == 403
        assert 'denied' in response['data']['error'].lower()

    @pytest.mark.asyncio
    async def test_allowed_command_succeeds(self, page: Page, test_server: str):
        """Test Step 3: Allowed command succeeds."""
        await page.goto(test_server)

        response = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/bash', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: 'ls -la'})
                });
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        assert response['status'] == 200
        assert response['data']['status'] == 'allowed'

    @pytest.mark.asyncio
    async def test_file_within_project_allowed(self, page: Page, test_server: str):
        """Test Step 4: File within project is allowed."""
        await page.goto(test_server)

        response = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/file/read', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({file_path: 'src/main.py'})
                });
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        assert response['status'] == 200
        assert response['data']['status'] == 'allowed'

    @pytest.mark.asyncio
    async def test_mcp_authorization_check(self, page: Page, test_server: str):
        """Test Step 5: MCP tool calls check authorization."""
        await page.goto(test_server)

        # Without auth token
        response_no_auth = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/mcp/call', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        tool_name: 'slack__send_message',
                        tool_input: {channel: '#general', message: 'test'}
                    })
                });
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        assert response_no_auth['status'] == 403

        # With auth token
        response_with_auth = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/mcp/call', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        tool_name: 'slack__send_message',
                        tool_input: {channel: '#general', message: 'test'},
                        auth_token: 'valid-arcade-token-12345'
                    })
                });
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        assert response_with_auth['status'] == 200

    @pytest.mark.asyncio
    async def test_malicious_inputs_rejected(self, page: Page, test_server: str):
        """Test Step 6: Malicious inputs are rejected."""
        await page.goto(test_server)

        # Test command injection
        response = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/bash', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: 'ls; rm -rf /'})
                });
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        assert response['status'] == 403

        # Test path traversal
        response2 = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/file/read', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({file_path: '../../../etc/passwd'})
                });
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        assert response2['status'] == 403

    @pytest.mark.asyncio
    async def test_no_information_leakage(self, page: Page, test_server: str):
        """Test Step 7: Error messages don't leak sensitive info."""
        await page.goto(test_server)

        response = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/file/read', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({file_path: '/etc/passwd'})
                });
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        # Error message should not contain sensitive paths
        error_text = json.dumps(response['data'])
        assert '/etc/passwd' not in error_text
        assert 'denied' in response['data']['error'].lower()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, page: Page, test_server: str):
        """Test Step 8: Concurrent requests are handled correctly."""
        await page.goto(test_server)

        # Make multiple concurrent requests
        results = await page.evaluate("""
            async () => {
                const requests = [
                    fetch('/api/security/bash', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({command: 'ls -la'})
                    }),
                    fetch('/api/security/bash', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({command: 'sudo rm -rf /'})
                    }),
                    fetch('/api/security/file/read', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({file_path: 'test.txt'})
                    }),
                    fetch('/api/security/file/read', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({file_path: '/etc/passwd'})
                    }),
                ];

                const responses = await Promise.all(requests);
                const data = await Promise.all(responses.map(r => r.json()));

                return responses.map((r, i) => ({
                    status: r.status,
                    data: data[i]
                }));
            }
        """)

        # Verify results
        assert len(results) == 4
        assert results[0]['status'] == 200  # ls -la allowed
        assert results[1]['status'] == 403  # sudo blocked
        assert results[2]['status'] == 200  # test.txt allowed
        assert results[3]['status'] == 403  # /etc/passwd blocked

    @pytest.mark.asyncio
    async def test_health_endpoint_accessible(self, page: Page, test_server: str):
        """Test that health endpoint is accessible."""
        await page.goto(test_server)

        response = await page.evaluate("""
            async () => {
                const response = await fetch('/api/health');
                return {
                    status: response.status,
                    data: await response.json()
                };
            }
        """)

        assert response['status'] == 200
        assert response['data']['status'] == 'ok'

    @pytest.mark.asyncio
    async def test_cors_headers_present(self, page: Page, test_server: str):
        """Test that CORS headers are present in responses."""
        await page.goto(test_server)

        response = await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/bash', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: 'ls -la'})
                });
                return {
                    status: response.status,
                    headers: Object.fromEntries(response.headers.entries())
                };
            }
        """)

        # Check CORS headers
        headers = response['headers']
        assert 'access-control-allow-origin' in headers

    @pytest.mark.asyncio
    async def test_screenshot_security_rejection(self, page: Page, test_server: str):
        """Take screenshot of security rejection."""
        await page.goto(test_server)

        # Execute a blocked command via console
        await page.evaluate("""
            async () => {
                const response = await fetch('/api/security/bash', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: 'sudo rm -rf /'})
                });
                const data = await response.json();
                console.error('Security Rejection:', data);
            }
        """)

        # Wait for console message
        await page.wait_for_timeout(1000)

        # Take screenshot
        screenshot_dir = Path(__file__).parent.parent / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)

        screenshot_path = screenshot_dir / "ai113_security_rejection.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)

        assert screenshot_path.exists()


# Run with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
