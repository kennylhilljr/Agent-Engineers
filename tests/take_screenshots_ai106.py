#!/usr/bin/env python3
"""
Take screenshots of dashboard for AI-106 verification.
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright


async def take_screenshots():
    """Start server and take screenshots."""
    # Start the dashboard server
    print("Starting dashboard server...")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "dashboard.server",
            "--port", "8766",
            "--host", "127.0.0.1"
        ],
        cwd="/Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-dashboard",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    print("Waiting for server to start...")
    await asyncio.sleep(3)

    screenshot_dir = Path("/Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-dashboard/screenshots")
    screenshot_dir.mkdir(exist_ok=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})

            # Screenshot 1: Health check endpoint
            print("Capturing health check...")
            await page.goto("http://127.0.0.1:8766/health")
            await page.wait_for_load_state("networkidle")
            await page.screenshot(
                path=str(screenshot_dir / "ai-106-health-check.png"),
                full_page=True
            )

            # Screenshot 2: Metrics API response
            print("Capturing metrics API...")
            await page.goto("http://127.0.0.1:8766/api/metrics?pretty")
            await page.wait_for_load_state("networkidle")
            await page.screenshot(
                path=str(screenshot_dir / "ai-106-metrics-api.png"),
                full_page=True
            )

            # Screenshot 3: Provider status
            print("Capturing provider status...")
            await page.goto("http://127.0.0.1:8766/api/providers/status")
            await page.wait_for_load_state("networkidle")
            await page.screenshot(
                path=str(screenshot_dir / "ai-106-provider-status.png"),
                full_page=True
            )

            # Screenshot 4: Specific agent (coding)
            print("Capturing coding agent...")
            await page.goto("http://127.0.0.1:8766/api/agents/coding?pretty")
            await page.wait_for_load_state("networkidle")
            await page.screenshot(
                path=str(screenshot_dir / "ai-106-coding-agent.png"),
                full_page=True
            )

            # Screenshot 5: All agents (via metrics endpoint - showing agents section)
            print("Verifying agent data...")
            await page.goto("http://127.0.0.1:8766/api/metrics")
            await page.wait_for_load_state("networkidle")
            content = await page.content()

            # Verify all 14 agents are present in the response
            response = await page.goto("http://127.0.0.1:8766/api/metrics")
            data = await response.json()

            agents = data.get("agents", {})
            expected_agents = [
                "orchestrator", "linear", "coding", "coding_fast", "github",
                "pr_reviewer", "pr_reviewer_fast", "ops", "slack",
                "chatgpt", "gemini", "groq", "kimi", "windsurf"
            ]

            print(f"\n{'='*60}")
            print("VERIFICATION RESULTS:")
            print(f"{'='*60}")
            print(f"Total agents in metrics: {len(agents)}")
            print(f"Expected agents: {len(expected_agents)}")

            for agent_name in expected_agents:
                status = "✓ FOUND" if agent_name in agents else "✗ MISSING"
                print(f"  {status}: {agent_name}")

                if agent_name in agents:
                    agent_data = agents[agent_name]
                    print(f"    - Invocations: {agent_data.get('total_invocations', 0)}")
                    print(f"    - Success Rate: {agent_data.get('success_rate', 0):.1%}")

            print(f"\n{'='*60}")
            print(f"Project: {data.get('project_name', 'N/A')}")
            print(f"Total Sessions: {data.get('total_sessions', 0)}")
            print(f"Total Tokens: {data.get('total_tokens', 0):,}")
            print(f"Total Cost: ${data.get('total_cost_usd', 0):.2f}")
            print(f"{'='*60}\n")

            await browser.close()

        print(f"\nScreenshots saved to: {screenshot_dir}")
        print("  - ai-106-health-check.png")
        print("  - ai-106-metrics-api.png")
        print("  - ai-106-provider-status.png")
        print("  - ai-106-coding-agent.png")

    finally:
        # Stop the server
        print("\nStopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Server stopped.")


if __name__ == "__main__":
    asyncio.run(take_screenshots())
