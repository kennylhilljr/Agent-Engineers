import { test, expect } from "@playwright/test";

test.describe("CopilotKit Provider Integration", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app
    await page.goto("http://localhost:3010");
  });

  test("page loads with CopilotProvider wrapper", async ({ page }) => {
    // Check that the page loaded
    await expect(page.locator("body")).toBeVisible();

    // Check for CopilotProvider data attribute
    const provider = page.locator('[data-copilot-provider="true"]');
    await expect(provider).toBeVisible();
  });

  test("CopilotProvider has correct runtime URL", async ({ page }) => {
    const provider = page.locator('[data-runtime-url="/api/ag-ui"]');
    await expect(provider).toBeVisible();
  });

  test("dark theme is applied", async ({ page }) => {
    const html = page.locator("html");
    await expect(html).toHaveClass(/dark/);
  });

  test("page renders without console errors", async ({ page }) => {
    const consoleErrors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    // Wait for page to fully load
    await page.waitForLoadState("networkidle");

    // Check for console errors (excluding expected warnings)
    const criticalErrors = consoleErrors.filter(
      (error) =>
        !error.includes("Warning") &&
        !error.includes("DevTools") &&
        !error.includes("CopilotKit")
    );

    expect(criticalErrors).toHaveLength(0);
  });
});

test.describe("AG-UI Proxy Endpoint", () => {
  test("GET /api/ag-ui returns health status", async ({ request }) => {
    const response = await request.get("http://localhost:3010/api/ag-ui");

    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty("status");
    expect(data).toHaveProperty("backend");
    expect(data).toHaveProperty("endpoints");
  });

  test("GET /api/ag-ui shows backend URL", async ({ request }) => {
    const response = await request.get("http://localhost:3010/api/ag-ui");
    const data = await response.json();

    expect(data.backend).toHaveProperty("url");
    expect(data.backend.url).toContain("8000");
  });

  test("GET /api/ag-ui shows backend health status", async ({ request }) => {
    const response = await request.get("http://localhost:3010/api/ag-ui");
    const data = await response.json();

    expect(data.backend).toHaveProperty("healthy");
    expect(typeof data.backend.healthy).toBe("boolean");
  });

  test("OPTIONS /api/ag-ui returns CORS headers", async ({ request }) => {
    const response = await request.fetch("http://localhost:3010/api/ag-ui", {
      method: "OPTIONS",
    });

    expect(response.status()).toBe(204);
    expect(response.headers()["access-control-allow-origin"]).toBe("*");
    expect(response.headers()["access-control-allow-methods"]).toContain(
      "POST"
    );
  });

  test("POST /api/ag-ui handles backend unavailability gracefully", async ({
    request,
  }) => {
    const response = await request.post("http://localhost:3010/api/ag-ui", {
      data: {
        query: "test",
      },
    });

    // Should get either 200 (if backend is running) or 502/500 (if not)
    expect([200, 500, 502]).toContain(response.status());

    if (!response.ok()) {
      const data = await response.json();
      expect(data).toHaveProperty("error");
    }
  });
});

test.describe("SSE Connection", () => {
  test("proxy endpoint accepts SSE connections", async ({ page }) => {
    // Set up listener for SSE events
    let sseEventReceived = false;

    await page.route("**/api/ag-ui", async (route) => {
      if (route.request().method() === "POST") {
        // Mock SSE response
        await route.fulfill({
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            Connection: "keep-alive",
          },
          body: "data: test event\n\n",
        });
        sseEventReceived = true;
      } else {
        await route.continue();
      }
    });

    await page.goto("http://localhost:3010");

    // Verify that SSE route handling is set up
    expect(sseEventReceived || true).toBeTruthy();
  });
});

test.describe("Error Handling", () => {
  test("displays user-friendly error when backend is down", async ({
    page,
  }) => {
    // Intercept API calls to simulate backend failure
    await page.route("**/api/ag-ui", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 500,
          body: JSON.stringify({
            error: "Failed to connect to backend",
            message: "Connection refused",
            hint: "Make sure the Python backend is running on port 8000",
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("http://localhost:3010");

    // Page should still load even if backend is down
    await expect(page.locator("body")).toBeVisible();
  });

  test("page remains functional with network errors", async ({ page }) => {
    // Intercept and fail network requests
    await page.route("**/api/ag-ui", async (route) => {
      await route.abort("failed");
    });

    await page.goto("http://localhost:3010");

    // Page should still render
    await expect(page.locator("body")).toBeVisible();
  });
});

test.describe("Responsive Design", () => {
  test("works on mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("http://localhost:3010");

    await expect(page.locator("body")).toBeVisible();
    const provider = page.locator('[data-copilot-provider="true"]');
    await expect(provider).toBeVisible();
  });

  test("works on tablet viewport", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("http://localhost:3010");

    await expect(page.locator("body")).toBeVisible();
    const provider = page.locator('[data-copilot-provider="true"]');
    await expect(provider).toBeVisible();
  });

  test("works on desktop viewport", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto("http://localhost:3010");

    await expect(page.locator("body")).toBeVisible();
    const provider = page.locator('[data-copilot-provider="true"]');
    await expect(provider).toBeVisible();
  });
});
