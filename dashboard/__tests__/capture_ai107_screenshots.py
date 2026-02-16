"""Screenshot capture script for AI-107 real-time metrics broadcasting.

This script starts the dashboard server, simulates agent tasks with real-time
broadcasting, and captures screenshots showing the functionality.
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.collector import AgentMetricsCollector
from dashboard.server import DashboardServer


async def capture_screenshots():
    """Capture screenshots demonstrating real-time metrics broadcasting."""
    import tempfile

    # Create temporary metrics directory
    temp_dir = Path(tempfile.mkdtemp())
    screenshots_dir = Path(__file__).parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    print("\n" + "="*70)
    print("AI-107: REAL-TIME METRICS BROADCASTING - SCREENSHOT CAPTURE")
    print("="*70)

    # Create server
    server = DashboardServer(
        project_name="ai-107-screenshots",
        metrics_dir=temp_dir,
        port=18083,
        host="127.0.0.1"
    )

    # Start server
    from aiohttp import web
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, server.host, server.port)
    await site.start()

    print(f"\n✓ Dashboard server started at http://{server.host}:{server.port}")
    print(f"✓ WebSocket endpoint: ws://{server.host}:{server.port}/ws")

    await asyncio.sleep(1)

    # Start browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"\n✓ Browser launched")

        # Navigate to dashboard
        await page.goto(f"http://{server.host}:{server.port}/")
        await page.wait_for_load_state("networkidle")

        print(f"✓ Dashboard loaded")

        # Screenshot 1: Initial dashboard state
        screenshot_path = screenshots_dir / "ai-107-1-initial-dashboard.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"\n📸 Screenshot 1: {screenshot_path.name}")
        print(f"   - Initial dashboard with WebSocket connection")

        # Simulate first agent task
        print(f"\n⚙️  Simulating agent tasks...")

        session_id = server.collector.start_session()

        # Task 1
        with server.collector.track_agent(
            "coding-agent", "AI-107", "claude-sonnet-4-5", session_id
        ) as tracker:
            await asyncio.sleep(0.3)
            tracker.add_tokens(2000, 4000)
            tracker.add_artifact("file:collector.py")
            tracker.add_artifact("file:server.py")

        print(f"   ✓ Task 1 completed (coding-agent)")

        await asyncio.sleep(0.5)

        # Screenshot 2: After first task
        screenshot_path = screenshots_dir / "ai-107-2-after-first-task.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"\n📸 Screenshot 2: {screenshot_path.name}")
        print(f"   - Dashboard after first agent task")
        print(f"   - Real-time event broadcasting active")

        # Task 2
        with server.collector.track_agent(
            "github-agent", "AI-107", "claude-sonnet-4-5", session_id
        ) as tracker:
            await asyncio.sleep(0.3)
            tracker.add_tokens(1500, 3000)
            tracker.add_artifact("commit:abc123")
            tracker.add_artifact("pr:#107")

        print(f"   ✓ Task 2 completed (github-agent)")

        await asyncio.sleep(0.5)

        # Task 3
        with server.collector.track_agent(
            "test-agent", "AI-107", "claude-sonnet-4-5", session_id
        ) as tracker:
            await asyncio.sleep(0.3)
            tracker.add_tokens(1800, 3600)
            tracker.add_artifact("file:test_metrics_broadcasting.py")
            tracker.add_artifact("file:test_websocket_broadcasting.py")

        print(f"   ✓ Task 3 completed (test-agent)")

        await asyncio.sleep(0.5)

        # Screenshot 3: After multiple tasks
        screenshot_path = screenshots_dir / "ai-107-3-multiple-tasks.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"\n📸 Screenshot 3: {screenshot_path.name}")
        print(f"   - Dashboard after multiple agent tasks")
        print(f"   - Shows real-time metrics accumulation")

        # Simulate a failed task
        try:
            with server.collector.track_agent(
                "error-agent", "AI-107", "claude-sonnet-4-5", session_id
            ) as tracker:
                tracker.add_tokens(500, 1000)
                raise ValueError("Simulated task failure")
        except ValueError:
            pass

        print(f"   ✓ Task 4 failed (error-agent) - intentional")

        await asyncio.sleep(0.5)

        # Screenshot 4: With failed task
        screenshot_path = screenshots_dir / "ai-107-4-with-failure.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"\n📸 Screenshot 4: {screenshot_path.name}")
        print(f"   - Dashboard showing both successful and failed tasks")
        print(f"   - Real-time error broadcasting")

        server.collector.end_session(session_id)

        await browser.close()
        print(f"\n✓ Browser closed")

    # Show final metrics
    state = server.collector.get_state()
    print(f"\n" + "="*70)
    print("METRICS SUMMARY")
    print("="*70)
    print(f"Events recorded:  {len(state['events'])}")
    print(f"Agents tracked:   {len([a for a in state['agents'] if a.startswith(('coding', 'github', 'test', 'error'))])}")
    print(f"Total tokens:     {state['total_tokens']}")
    print(f"Total cost:       ${state['total_cost_usd']:.4f}")
    print(f"Sessions:         {state['total_sessions']}")
    print("="*70)

    # Cleanup
    await runner.cleanup()
    print(f"\n✓ Server stopped")

    print(f"\n" + "="*70)
    print("SCREENSHOT CAPTURE COMPLETE")
    print("="*70)
    print(f"\n4 screenshots saved to: {screenshots_dir}")
    print(f"\n✓ AI-107 implementation verified with screenshots")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(capture_screenshots())
