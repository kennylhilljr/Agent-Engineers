import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { chromium, Browser, Page } from 'playwright';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';

/**
 * KAN-47: Browser E2E Tests
 *
 * Verifies that:
 * 1. Dev server starts successfully on port 3010
 * 2. Application loads in the browser
 * 3. Dark theme is applied
 * 4. All feature cards are visible
 */

describe('KAN-47: Browser E2E Tests', () => {
  let browser: Browser;
  let page: Page;
  let devServer: ChildProcess | null = null;
  const PORT = 3010;
  const BASE_URL = `http://localhost:${PORT}`;

  beforeAll(async () => {
    // Start the dev server
    const projectRoot = path.resolve(__dirname, '..');

    devServer = spawn('npm', ['run', 'dev'], {
      cwd: projectRoot,
      shell: true,
      stdio: 'pipe',
    });

    // Wait for server to be ready
    await new Promise<void>((resolve) => {
      const checkServer = async () => {
        try {
          const response = await fetch(BASE_URL);
          if (response.ok) {
            resolve();
          } else {
            setTimeout(checkServer, 500);
          }
        } catch {
          setTimeout(checkServer, 500);
        }
      };
      checkServer();
    });

    // Launch browser
    browser = await chromium.launch();
  }, 60000); // 60 second timeout for server startup

  afterAll(async () => {
    // Close browser
    if (browser) {
      await browser.close();
    }

    // Stop dev server
    if (devServer) {
      devServer.kill('SIGTERM');
      // Give it time to shut down gracefully
      await new Promise(resolve => setTimeout(resolve, 2000));
      if (devServer.killed === false) {
        devServer.kill('SIGKILL');
      }
    }
  });

  it('should load the homepage on port 3010', async () => {
    page = await browser.newPage();
    const response = await page.goto(BASE_URL);

    expect(response?.status()).toBe(200);
    await page.close();
  }, 30000);

  it('should display the main heading', async () => {
    page = await browser.newPage();
    await page.goto(BASE_URL);

    const heading = await page.textContent('h1');
    expect(heading).toContain('AI Coding Dashboard');

    await page.close();
  }, 30000);

  it('should have dark theme background applied', async () => {
    page = await browser.newPage();
    await page.goto(BASE_URL);

    const main = await page.locator('main');
    const classes = await main.getAttribute('class');

    expect(classes).toContain('bg-gray-900');

    await page.close();
  }, 30000);

  it('should display Next.js 14 feature card', async () => {
    page = await browser.newPage();
    await page.goto(BASE_URL);

    const nextjsCard = await page.getByText('Next.js 14');
    expect(await nextjsCard.isVisible()).toBe(true);

    await page.close();
  }, 30000);

  it('should display TypeScript feature card', async () => {
    page = await browser.newPage();
    await page.goto(BASE_URL);

    const tsCard = await page.getByText('TypeScript');
    expect(await tsCard.isVisible()).toBe(true);

    await page.close();
  }, 30000);

  it('should display Tailwind CSS feature card', async () => {
    page = await browser.newPage();
    await page.goto(BASE_URL);

    const tailwindCard = await page.getByText('Tailwind CSS');
    expect(await tailwindCard.isVisible()).toBe(true);

    await page.close();
  }, 30000);

  it('should display CopilotKit feature card', async () => {
    page = await browser.newPage();
    await page.goto(BASE_URL);

    const copilotCard = await page.getByText('CopilotKit');
    expect(await copilotCard.isVisible()).toBe(true);

    await page.close();
  }, 30000);

  it('should have no console errors on page load', async () => {
    const consoleErrors: string[] = [];

    page = await browser.newPage();
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    expect(consoleErrors).toHaveLength(0);

    await page.close();
  }, 30000);

  it('should have responsive viewport meta tag', async () => {
    page = await browser.newPage();
    await page.goto(BASE_URL);

    const viewport = await page.locator('meta[name="viewport"]');
    const content = await viewport.getAttribute('content');

    expect(content).toContain('width=device-width');
    expect(content).toContain('initial-scale=1');

    await page.close();
  }, 30000);
});
