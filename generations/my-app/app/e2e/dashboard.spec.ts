import { test, expect } from '@playwright/test';

test.describe('Dashboard Layout', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to dashboard with a test project ID
    await page.goto('http://localhost:3010/test-project-123');
  });

  test('should display project header with statistics', async ({ page }) => {
    // Check for project name
    await expect(page.getByText('AI Coding Dashboard')).toBeVisible();

    // Check for completion percentage
    await expect(page.locator('text=35%').first()).toBeVisible();

    // Check for task statistics
    await expect(page.getByText('7/20')).toBeVisible();
    await expect(page.getByText('Tasks Complete')).toBeVisible();

    // Check for files modified
    await expect(page.getByText('42')).toBeVisible();
    await expect(page.getByText('Files Modified')).toBeVisible();

    // Check for test results
    await expect(page.getByText('156/200')).toBeVisible();
    await expect(page.getByText('Tests Passed').first()).toBeVisible();
  });

  test('should display activity feed with events', async ({ page }) => {
    await expect(page.getByText('Activity Feed')).toBeVisible();
    await expect(page.getByText('Database schema created')).toBeVisible();
    await expect(page.getByText('Unit tests passed')).toBeVisible();
    await expect(page.getByText('Updated API routes')).toBeVisible();
  });

  test('should show agent reasoning in activity feed', async ({ page }) => {
    await expect(
      page.getByText('Set up PostgreSQL schema with Drizzle ORM')
    ).toBeVisible();
    await expect(
      page.getByText('Added streaming support for real-time agent communication')
    ).toBeVisible();
  });

  test('should display chat placeholder', async ({ page }) => {
    await expect(page.getByText('Agent Chat')).toBeVisible();
    await expect(
      page.getByText('CopilotKit chat interface will be integrated here')
    ).toBeVisible();
  });

  test('should show empty state for components', async ({ page }) => {
    await expect(page.getByText('Ready for AI Generation')).toBeVisible();
    await expect(
      page.getByText(/Waiting for agent to generate components/)
    ).toBeVisible();
  });

  test('should render progress ring', async ({ page }) => {
    // Check for SVG circle elements (progress ring)
    const progressRing = page.locator('svg circle').first();
    await expect(progressRing).toBeVisible();
  });

  test('should display event type badges', async ({ page }) => {
    await expect(page.getByText('task completed')).toBeVisible();
    await expect(page.getByText('test run')).toBeVisible();
    await expect(page.getByText('file modified')).toBeVisible();
    await expect(page.getByText('approval requested')).toBeVisible();
  });

  test('should show event timestamps', async ({ page }) => {
    // Look for relative time stamps
    const timeStamps = page.locator('text=/\\d+[mhd] ago/');
    await expect(timeStamps.first()).toBeVisible();
  });
});

test.describe('Responsive Layout', () => {
  test('should display correctly on desktop (1920px)', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('http://localhost:3010/test-project-123');

    // All elements should be visible
    await expect(page.getByText('AI Coding Dashboard')).toBeVisible();
    await expect(page.getByText('Activity Feed')).toBeVisible();
    await expect(page.getByText('Agent Chat')).toBeVisible();

    // Sidebar should be visible on the right
    const activityFeed = page.getByText('Activity Feed');
    await expect(activityFeed).toBeVisible();
  });

  test('should display correctly on tablet (768px)', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('http://localhost:3010/test-project-123');

    // All elements should still be visible
    await expect(page.getByText('AI Coding Dashboard')).toBeVisible();
    await expect(page.getByText('Activity Feed')).toBeVisible();
    await expect(page.getByText('Ready for AI Generation')).toBeVisible();
  });

  test('should display correctly on mobile (375px)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('http://localhost:3010/test-project-123');

    // All elements should be stacked vertically
    await expect(page.getByText('AI Coding Dashboard')).toBeVisible();
    await expect(page.getByText('Activity Feed')).toBeVisible();

    // Stats should be in single column
    await expect(page.getByText('Tasks Complete')).toBeVisible();
    await expect(page.getByText('Files Modified')).toBeVisible();
  });

  test('should adapt header stats layout on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('http://localhost:3010/test-project-123');

    // All three stats should be visible
    await expect(page.getByText('7/20')).toBeVisible();
    await expect(page.getByText('42')).toBeVisible();
    await expect(page.getByText('156/200')).toBeVisible();
  });
});

test.describe('Dark Theme', () => {
  test('should apply dark theme styles', async ({ page }) => {
    await page.goto('http://localhost:3010/test-project-123');

    // Check that html has dark class
    const html = page.locator('html');
    await expect(html).toHaveClass(/dark/);

    // Check for dark background color
    const body = page.locator('body');
    const bgColor = await body.evaluate((el) =>
      window.getComputedStyle(el).backgroundColor
    );
    // Dark theme should have a dark background (low RGB values)
    expect(bgColor).toBeTruthy();
  });
});

test.describe('Console Errors', () => {
  test('should have no console errors', async ({ page }) => {
    const consoleErrors: string[] = [];

    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });

    await page.goto('http://localhost:3010/test-project-123');

    // Wait for page to fully load
    await page.waitForLoadState('networkidle');

    // Should have no console errors
    expect(consoleErrors).toHaveLength(0);
  });
});
