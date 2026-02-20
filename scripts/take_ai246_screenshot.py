"""Script to start the server, seed audit data, and take a Playwright screenshot (AI-246)."""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from audit.models import get_audit_store, reset_audit_store
from audit.events import (
    AUTH_LOGIN, AUTH_LOGOUT, AUTH_LOGIN_FAILED, AUTH_API_KEY_CREATED,
    TEAM_MEMBER_INVITED, TEAM_ROLE_CHANGED, TEAM_MEMBER_REMOVED,
    AGENT_SESSION_STARTED, AGENT_SESSION_COMPLETED, AGENT_SESSION_FAILED,
    BILLING_PLAN_UPGRADED, BILLING_PAYMENT_SUCCEEDED,
)
from datetime import datetime, timezone, timedelta


def seed_audit_data():
    """Insert realistic sample events so the UI has data to display."""
    reset_audit_store()
    store = get_audit_store()
    now = datetime.now(timezone.utc)

    events = [
        ("org1", "alice@example.com", AUTH_LOGIN, "user_alice", {"method": "password", "ip": "203.0.113.42"}),
        ("org1", "bob@example.com", AUTH_LOGIN, "user_bob", {"method": "sso", "provider": "google"}),
        ("org1", "alice@example.com", TEAM_MEMBER_INVITED, "invite_abc123", {"email": "charlie@example.com", "role": "member"}),
        ("org1", "alice@example.com", TEAM_ROLE_CHANGED, "user_bob", {"old_role": "member", "new_role": "admin"}),
        ("org1", "system", AGENT_SESSION_STARTED, "session_001", {"agent": "coding", "ticket": "AI-246"}),
        ("org1", "system", AGENT_SESSION_COMPLETED, "session_001", {"agent": "coding", "duration_s": 142.5, "tokens": 8420}),
        ("org1", "system", BILLING_PLAN_UPGRADED, "sub_xyz789", {"from_plan": "starter", "to_plan": "organization", "amount_usd": 149.00}),
        ("org1", "mallory@evil.com", AUTH_LOGIN_FAILED, "user_unknown", {"ip": "198.51.100.7", "reason": "invalid_password"}),
        ("org1", "system", AGENT_SESSION_STARTED, "session_002", {"agent": "github", "ticket": "AI-245"}),
        ("org1", "system", AGENT_SESSION_FAILED, "session_002", {"agent": "github", "error": "rate_limit_exceeded"}),
        ("org1", "alice@example.com", AUTH_API_KEY_CREATED, "key_deploy_001", {"key_name": "ci-deploy", "scopes": ["read", "write"]}),
        ("org1", "bob@example.com", TEAM_MEMBER_REMOVED, "user_charlie", {"role": "member", "reason": "offboarding"}),
        ("org1", "system", BILLING_PAYMENT_SUCCEEDED, "pi_3NkAbCd", {"amount_usd": 149.00, "currency": "usd"}),
        ("org1", "alice@example.com", AUTH_LOGOUT, "user_alice", {"session_duration_s": 3600}),
    ]

    for i, (org_id, actor_id, event_type, resource_id, details) in enumerate(events):
        ts = now - timedelta(hours=len(events) - i)
        store.record(
            org_id=org_id,
            actor_id=actor_id,
            event_type=event_type,
            resource_id=resource_id,
            details=details,
            timestamp=ts,
        )
    print(f"Seeded {store.total_count} audit events.")


async def take_screenshot():
    """Start a minimal aiohttp server and take a Playwright screenshot."""
    from aiohttp import web
    from audit.routes import register_audit_routes

    app = web.Application()
    register_audit_routes(app)

    # Also serve the HTML page directly
    from pathlib import Path as P
    html_path = P(__file__).parent / "dashboard" / "audit_log.html"

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 9246)
    await site.start()
    print("Server started at http://127.0.0.1:9246")

    # Give it a moment
    await asyncio.sleep(0.5)

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1400, "height": 900})
            await page.goto("http://127.0.0.1:9246/settings/audit-log")
            await page.wait_for_timeout(2000)  # let JS load data
            screenshot_path = str(P(__file__).parent / "screenshots" / "ai-246-audit-log.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved: {screenshot_path}")
            await browser.close()
    except ImportError:
        print("Playwright not available - skipping browser screenshot")
    except Exception as e:
        print(f"Screenshot failed: {e}")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    seed_audit_data()
    asyncio.run(take_screenshot())
