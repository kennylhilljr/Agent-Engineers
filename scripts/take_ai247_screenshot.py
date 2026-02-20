"""Script to start the server, seed pricing data, and take a Playwright screenshot (AI-247).

Demonstrates the 5-tier pricing page with monthly/annual toggle live in a browser.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def take_screenshot():
    """Start a minimal aiohttp server and take a Playwright screenshot of the pricing page."""
    from aiohttp import web
    from billing.routes import register_billing_routes

    app = web.Application()
    register_billing_routes(app)

    # Serve the pricing HTML at root for easy screenshot
    async def serve_pricing(request):
        pricing_html = Path(__file__).parent.parent / "dashboard" / "pricing.html"
        if pricing_html.exists():
            return web.Response(
                text=pricing_html.read_text(encoding="utf-8"),
                content_type="text/html",
            )
        return web.Response(text="<h1>pricing.html not found</h1>", content_type="text/html")

    app.router.add_get("/", serve_pricing)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8099)
    await site.start()
    print("Server running on http://localhost:8099")

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.goto("http://localhost:8099/pricing")
            await page.wait_for_load_state("networkidle")

            screenshots_dir = Path(__file__).parent.parent / "screenshots"
            screenshots_dir.mkdir(exist_ok=True)

            # Screenshot: monthly billing
            monthly_path = screenshots_dir / "ai247_pricing_monthly.png"
            await page.screenshot(path=str(monthly_path), full_page=True)
            print(f"Monthly screenshot saved: {monthly_path}")

            # Screenshot: annual billing (click the toggle)
            await page.click("#btn-annual")
            await page.wait_for_timeout(300)
            annual_path = screenshots_dir / "ai247_pricing_annual.png"
            await page.screenshot(path=str(annual_path), full_page=True)
            print(f"Annual screenshot saved: {annual_path}")

            await browser.close()
    except ImportError:
        print("Playwright not installed. Install with: pip install playwright && playwright install chromium")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(take_screenshot())
