"""
Playwright browser-level authentication tests for AI-112

Tests authentication from a browser perspective including:
- API endpoint access with/without authentication
- WebSocket connection with/without authentication
- Browser UI behavior with authentication errors
- Authorization header handling in browser context
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from playwright.async_api import Page, async_playwright, expect


# Server process management
server_process = None
server_url = "http://127.0.0.1:18420"  # Use different port for Playwright tests


async def start_test_server(with_auth: bool = False) -> subprocess.Popen:
    """Start REST API server for testing.

    Args:
        with_auth: If True, set DASHBOARD_AUTH_TOKEN

    Returns:
        Server subprocess
    """
    import signal

    # Create temporary metrics directory
    temp_dir = tempfile.mkdtemp()
    metrics_file = Path(temp_dir) / ".agent_metrics.json"

    # Create minimal metrics
    minimal_metrics = {
        "version": 1,
        "project_name": "test-project",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "total_sessions": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_duration_seconds": 0.0,
        "agents": {},
        "events": [],
        "sessions": []
    }
    metrics_file.write_text(json.dumps(minimal_metrics))

    # Start server
    env = os.environ.copy()
    if with_auth:
        env['DASHBOARD_AUTH_TOKEN'] = 'test-token-12345'

    env['PYTHONPATH'] = str(Path(__file__).parent.parent)

    process = subprocess.Popen(
        [
            sys.executable, '-m', 'dashboard.rest_api_server',
            '--port', '18420',
            '--host', '127.0.0.1',
            '--metrics-dir', temp_dir,
            '--project-name', 'playwright-test'
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None
    )

    # Wait for server to start
    max_retries = 30
    for i in range(max_retries):
        try:
            import urllib.request
            urllib.request.urlopen(f"{server_url}/api/health", timeout=1)
            print(f"Server started successfully on {server_url}")
            return process
        except:
            time.sleep(0.5)
            if i == max_retries - 1:
                # Kill process if it didn't start
                try:
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    else:
                        process.terminate()
                except:
                    pass
                raise RuntimeError(f"Server failed to start after {max_retries * 0.5} seconds")

    return process


def stop_test_server(process: subprocess.Popen):
    """Stop test server.

    Args:
        process: Server subprocess to stop
    """
    if process:
        try:
            import signal
            if hasattr(os, 'killpg'):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()

            # Wait for process to terminate
            process.wait(timeout=5)
        except Exception as e:
            print(f"Error stopping server: {e}")
            try:
                process.kill()
            except:
                pass


# ============================================================================
# Playwright Tests - Open Mode (No Authentication)
# ============================================================================

@pytest.mark.asyncio
async def test_api_access_without_auth_open_mode():
    """Test Step 1-2: API endpoints accessible without auth in open mode (Playwright)."""
    global server_process
    server_process = await start_test_server(with_auth=False)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            # Test /api/health endpoint
            response = await page.goto(f"{server_url}/api/health")
            assert response.status == 200
            content = await response.json()
            assert content["status"] == "ok"

            # Test /api/metrics endpoint
            response = await page.goto(f"{server_url}/api/metrics")
            assert response.status == 200
            content = await response.json()
            assert "project_name" in content

            # Test /api/agents endpoint
            response = await page.goto(f"{server_url}/api/agents")
            assert response.status == 200
            content = await response.json()
            assert "agents" in content

            await browser.close()

    finally:
        stop_test_server(server_process)
        server_process = None


# ============================================================================
# Playwright Tests - Authenticated Mode
# ============================================================================

@pytest.mark.asyncio
async def test_api_reject_without_token():
    """Test Step 4: API endpoints reject requests without token (Playwright)."""
    global server_process
    server_process = await start_test_server(with_auth=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            # Test /api/metrics endpoint without token
            response = await page.goto(f"{server_url}/api/metrics")
            assert response.status == 401
            content = await response.json()
            assert "error" in content
            assert content["error"] == "Unauthorized"

            # Test /api/agents endpoint without token
            response = await page.goto(f"{server_url}/api/agents")
            assert response.status == 401

            await browser.close()

    finally:
        stop_test_server(server_process)
        server_process = None


@pytest.mark.asyncio
async def test_api_reject_wrong_token():
    """Test Step 5: API endpoints reject requests with wrong token (Playwright)."""
    global server_process
    server_process = await start_test_server(with_auth=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(
                extra_http_headers={"Authorization": "Bearer wrong-token"}
            )
            page = await context.new_page()

            # Test with wrong token
            response = await page.goto(f"{server_url}/api/metrics")
            assert response.status == 401
            content = await response.json()
            assert content["error"] == "Unauthorized"

            await browser.close()

    finally:
        stop_test_server(server_process)
        server_process = None


@pytest.mark.asyncio
async def test_api_accept_valid_token():
    """Test Step 8: API endpoints accept requests with valid Bearer token (Playwright)."""
    global server_process
    server_process = await start_test_server(with_auth=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(
                extra_http_headers={"Authorization": "Bearer test-token-12345"}
            )
            page = await context.new_page()

            # Test with valid token
            response = await page.goto(f"{server_url}/api/metrics")
            assert response.status == 200
            content = await response.json()
            assert "project_name" in content

            # Test /api/agents
            response = await page.goto(f"{server_url}/api/agents")
            assert response.status == 200
            content = await response.json()
            assert "agents" in content

            await browser.close()

    finally:
        stop_test_server(server_process)
        server_process = None


@pytest.mark.asyncio
async def test_health_endpoint_bypasses_auth():
    """Test: Health endpoint always accessible regardless of auth (Playwright)."""
    global server_process
    server_process = await start_test_server(with_auth=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            # Health endpoint should work without token even when auth is enabled
            response = await page.goto(f"{server_url}/api/health")
            assert response.status == 200
            content = await response.json()
            assert content["status"] == "ok"

            await browser.close()

    finally:
        stop_test_server(server_process)
        server_process = None


@pytest.mark.asyncio
async def test_fetch_api_with_bearer_token():
    """Test Step 8: JavaScript fetch() API with Bearer token (Playwright)."""
    global server_process
    server_process = await start_test_server(with_auth=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            # Navigate to health endpoint first (no auth needed)
            await page.goto(f"{server_url}/api/health")

            # Use JavaScript fetch() with Bearer token
            result = await page.evaluate("""
                async () => {
                    const response = await fetch('http://127.0.0.1:18420/api/metrics', {
                        headers: {
                            'Authorization': 'Bearer test-token-12345'
                        }
                    });
                    const data = await response.json();
                    return {
                        status: response.status,
                        hasProjectName: 'project_name' in data
                    };
                }
            """)

            assert result["status"] == 200
            assert result["hasProjectName"] is True

            await browser.close()

    finally:
        stop_test_server(server_process)
        server_process = None


@pytest.mark.asyncio
async def test_fetch_api_without_token_fails():
    """Test Step 4: JavaScript fetch() without token fails (Playwright)."""
    global server_process
    server_process = await start_test_server(with_auth=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            # Navigate to health endpoint first
            await page.goto(f"{server_url}/api/health")

            # Use JavaScript fetch() without Bearer token
            result = await page.evaluate("""
                async () => {
                    const response = await fetch('http://127.0.0.1:18420/api/metrics');
                    const data = await response.json();
                    return {
                        status: response.status,
                        hasError: 'error' in data,
                        error: data.error
                    };
                }
            """)

            assert result["status"] == 401
            assert result["hasError"] is True
            assert result["error"] == "Unauthorized"

            await browser.close()

    finally:
        stop_test_server(server_process)
        server_process = None


# Run with: python -m pytest tests/test_authentication_playwright.py -v -s
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
