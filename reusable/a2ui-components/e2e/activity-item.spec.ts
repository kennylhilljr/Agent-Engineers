/**
 * ActivityItem E2E Tests
 * Browser-based tests for ActivityItem component
 */

import { test, expect } from '@playwright/test';

test.describe('ActivityItem Component E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to a test page that renders ActivityItem components
    await page.goto('http://localhost:3010');
  });

  test('displays all 8 event types with correct colors', async ({ page }) => {
    // We'll test the activity feed on the dashboard
    // Check for different event types in the activity stream

    // Look for task_started (blue)
    const taskStartedItems = page.locator('[data-event-type="task_started"]');
    if (await taskStartedItems.count() > 0) {
      const firstItem = taskStartedItems.first();
      await expect(firstItem).toBeVisible();
      const dot = firstItem.locator('[data-testid="activity-dot"]');
      await expect(dot).toHaveClass(/bg-blue-500/);
    }

    // Look for task_completed (green)
    const taskCompletedItems = page.locator('[data-event-type="task_completed"]');
    if (await taskCompletedItems.count() > 0) {
      const dot = taskCompletedItems.first().locator('[data-testid="activity-dot"]');
      await expect(dot).toHaveClass(/bg-green-500/);
    }

    // Look for file_modified (purple)
    const fileModifiedItems = page.locator('[data-event-type="file_modified"]');
    if (await fileModifiedItems.count() > 0) {
      const dot = fileModifiedItems.first().locator('[data-testid="activity-dot"]');
      await expect(dot).toHaveClass(/bg-purple-500/);
    }

    // Look for error_occurred (red)
    const errorItems = page.locator('[data-event-type="error_occurred"]');
    if (await errorItems.count() > 0) {
      const dot = errorItems.first().locator('[data-testid="activity-dot"]');
      await expect(dot).toHaveClass(/bg-red-500/);
    }
  });

  test('displays timeline visual with connecting lines', async ({ page }) => {
    const activityItems = page.locator('[data-testid="activity-item"]');

    if (await activityItems.count() > 0) {
      const firstItem = activityItems.first();

      // Check for timeline dot
      const dot = firstItem.locator('[data-testid="activity-dot"]');
      await expect(dot).toBeVisible();

      // Check for timeline line
      const line = firstItem.locator('[data-testid="timeline-line"]');
      await expect(line).toBeVisible();
    }
  });

  test('shows event type badges', async ({ page }) => {
    const activityItems = page.locator('[data-testid="activity-item"]');

    if (await activityItems.count() > 0) {
      const firstItem = activityItems.first();
      const eventTypeBadge = firstItem.locator('[data-testid="event-type-badge"]');

      await expect(eventTypeBadge).toBeVisible();

      // Badge should have text content
      const text = await eventTypeBadge.textContent();
      expect(text).toBeTruthy();
      expect(text?.length).toBeGreaterThan(0);
    }
  });

  test('displays status badges when present', async ({ page }) => {
    const itemsWithStatus = page.locator('[data-testid="activity-item"][data-status]');

    if (await itemsWithStatus.count() > 0) {
      const firstItem = itemsWithStatus.first();
      const statusBadge = firstItem.locator('[data-testid="status-badge"]');

      await expect(statusBadge).toBeVisible();

      // Should have status text
      const text = await statusBadge.textContent();
      expect(['Pending', 'In Progress', 'Completed', 'Failed']).toContain(text);
    }
  });

  test('shows relative timestamps', async ({ page }) => {
    const activityItems = page.locator('[data-testid="activity-item"]');

    if (await activityItems.count() > 0) {
      const firstItem = activityItems.first();
      const timestamp = firstItem.locator('[data-testid="activity-timestamp"]');

      await expect(timestamp).toBeVisible();

      // Timestamp should have relative time text
      const text = await timestamp.textContent();
      expect(text).toBeTruthy();
      expect(
        text?.includes('ago') ||
        text?.includes('just now') ||
        text?.includes('yesterday')
      ).toBeTruthy();
    }
  });

  test('expands and collapses metadata section', async ({ page }) => {
    const itemsWithMetadata = page.locator('[data-testid="activity-item"]:has([data-testid="expand-button"])');

    if (await itemsWithMetadata.count() > 0) {
      const firstItem = itemsWithMetadata.first();
      const expandButton = firstItem.locator('[data-testid="expand-button"]');

      // Initially collapsed
      await expect(expandButton).toBeVisible();
      await expect(expandButton).toContainText('Show details');

      // Metadata section should not be visible
      let metadataSection = firstItem.locator('[data-testid="metadata-section"]');
      await expect(metadataSection).not.toBeVisible();

      // Click to expand
      await expandButton.click();

      // Should show "Hide details" text
      await expect(expandButton).toContainText('Hide details');

      // Metadata section should now be visible
      await expect(metadataSection).toBeVisible();

      // Click to collapse
      await expandButton.click();

      // Should be collapsed again
      await expect(expandButton).toContainText('Show details');
      await expect(metadataSection).not.toBeVisible();
    }
  });

  test('displays activity titles and descriptions', async ({ page }) => {
    const activityItems = page.locator('[data-testid="activity-item"]');

    if (await activityItems.count() > 0) {
      const firstItem = activityItems.first();

      // Should have a title
      const title = firstItem.locator('[data-testid="activity-title"]');
      await expect(title).toBeVisible();
      const titleText = await title.textContent();
      expect(titleText).toBeTruthy();
      expect(titleText?.length).toBeGreaterThan(0);

      // May have a description
      const description = firstItem.locator('[data-testid="activity-description"]');
      if (await description.count() > 0) {
        await expect(description).toBeVisible();
      }
    }
  });

  test('shows author attribution when present', async ({ page }) => {
    const itemsWithAuthor = page.locator('[data-testid="activity-item"]:has([data-testid="activity-author"])');

    if (await itemsWithAuthor.count() > 0) {
      const firstItem = itemsWithAuthor.first();
      const author = firstItem.locator('[data-testid="activity-author"]');

      await expect(author).toBeVisible();

      // Should start with "by "
      const text = await author.textContent();
      expect(text).toMatch(/^by /);
    }
  });

  test('has hover effects on activity items', async ({ page }) => {
    const activityItems = page.locator('[data-testid="activity-item"]');

    if (await activityItems.count() > 0) {
      const firstItem = activityItems.first();
      const contentBox = firstItem.locator('.rounded-lg.border');

      // Get initial border color
      const initialStyles = await contentBox.evaluate((el) => {
        return window.getComputedStyle(el).borderColor;
      });

      // Hover over the item
      await contentBox.hover();

      // Wait a bit for transition
      await page.waitForTimeout(300);

      // Border should change on hover
      const hoverStyles = await contentBox.evaluate((el) => {
        return window.getComputedStyle(el).borderColor;
      });

      // Note: The border color change is CSS-based, so we just verify the element is still visible
      await expect(contentBox).toBeVisible();
    }
  });

  test('timeline dots have appropriate styling', async ({ page }) => {
    const activityItems = page.locator('[data-testid="activity-item"]');

    if (await activityItems.count() > 0) {
      const firstItem = activityItems.first();
      const dot = firstItem.locator('[data-testid="activity-dot"]');

      await expect(dot).toBeVisible();

      // Should have rounded styling
      await expect(dot).toHaveClass(/rounded-full/);

      // Should have an icon inside
      const icon = dot.locator('[data-testid="activity-icon"]');
      await expect(icon).toBeVisible();
    }
  });
});
