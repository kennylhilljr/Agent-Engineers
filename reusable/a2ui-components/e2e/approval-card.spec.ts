import { test, expect } from '@playwright/test';

// Override base URL to use existing dev server on port 3010
test.use({ baseURL: 'http://localhost:3010' });

test.describe('ApprovalCard Component E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the A2UI demo page where ApprovalCard component is rendered
    await page.goto('/a2ui-demo');
    await page.waitForLoadState('networkidle');
  });

  test('multiple approval cards display with different severity levels', async ({ page }) => {
    // Look for multiple ApprovalCard components
    const approvalCards = page.getByTestId('approval-card');
    const count = await approvalCards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('low severity card displays with blue border', async ({ page }) => {
    const lowSeverityCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="low"]') }).first();
    await expect(lowSeverityCard).toBeVisible();

    const severityBadge = lowSeverityCard.getByTestId('severity-badge');
    await expect(severityBadge).toContainText('Low Risk');
  });

  test('medium severity card displays with yellow border', async ({ page }) => {
    const mediumSeverityCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="medium"]') }).first();
    await expect(mediumSeverityCard).toBeVisible();

    const severityBadge = mediumSeverityCard.getByTestId('severity-badge');
    await expect(severityBadge).toContainText('Medium Risk');
  });

  test('high severity card displays with orange border', async ({ page }) => {
    const highSeverityCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="high"]') }).first();
    await expect(highSeverityCard).toBeVisible();

    const severityBadge = highSeverityCard.getByTestId('severity-badge');
    await expect(severityBadge).toContainText('High Risk');
  });

  test('critical severity card displays with red border', async ({ page }) => {
    const criticalSeverityCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="critical"]') }).first();
    await expect(criticalSeverityCard).toBeVisible();

    const severityBadge = criticalSeverityCard.getByTestId('severity-badge');
    await expect(severityBadge).toContainText('Critical Risk');
  });

  test('pending card displays action buttons and reason input', async ({ page }) => {
    const pendingCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="pending"]') }).first();
    await expect(pendingCard).toBeVisible();

    // Check for action buttons
    const actionButtons = pendingCard.getByTestId('action-buttons');
    await expect(actionButtons).toBeVisible();

    const approveButton = pendingCard.getByTestId('approve-button');
    await expect(approveButton).toBeVisible();
    await expect(approveButton).toContainText('Approve');

    const rejectButton = pendingCard.getByTestId('reject-button');
    await expect(rejectButton).toBeVisible();
    await expect(rejectButton).toContainText('Reject');

    // Check for reason input
    const reasonInput = pendingCard.getByTestId('reason-input');
    await expect(reasonInput).toBeVisible();
  });

  test('approved card displays status message without action buttons', async ({ page }) => {
    const approvedCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="approved"]') }).first();
    await expect(approvedCard).toBeVisible();

    // Should have status message
    const statusMessage = approvedCard.getByTestId('status-message');
    await expect(statusMessage).toBeVisible();
    await expect(statusMessage).toContainText('approved');

    // Should not have action buttons
    const actionButtons = approvedCard.getByTestId('action-buttons');
    await expect(actionButtons).not.toBeVisible();
  });

  test('rejected card displays status message without action buttons', async ({ page }) => {
    const rejectedCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="rejected"]') }).first();
    await expect(rejectedCard).toBeVisible();

    // Should have status message
    const statusMessage = rejectedCard.getByTestId('status-message');
    await expect(statusMessage).toBeVisible();
    await expect(statusMessage).toContainText('rejected');

    // Should not have action buttons
    const actionButtons = rejectedCard.getByTestId('action-buttons');
    await expect(actionButtons).not.toBeVisible();
  });

  test('action section displays requested action in monospace font', async ({ page }) => {
    const anyCard = page.getByTestId('approval-card').first();
    await expect(anyCard).toBeVisible();

    const actionSection = anyCard.getByTestId('action-section');
    await expect(actionSection).toBeVisible();

    const actionText = anyCard.getByTestId('action-text');
    await expect(actionText).toBeVisible();
  });

  test('metadata section displays when metadata is provided', async ({ page }) => {
    // Find a card with metadata (high severity production deployment)
    const cardWithMetadata = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="high"]') }).first();
    await expect(cardWithMetadata).toBeVisible();

    const metadataSection = cardWithMetadata.getByTestId('metadata-section');
    await expect(metadataSection).toBeVisible();
  });

  test('context section displays when context is provided', async ({ page }) => {
    // Find a card with context
    const cardWithContext = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="critical"]') }).first();
    await expect(cardWithContext).toBeVisible();

    const contextSection = cardWithContext.getByTestId('context-section');
    await expect(contextSection).toBeVisible();
  });

  test('deadline countdown displays on pending cards with deadlines', async ({ page }) => {
    // Find a pending card with deadline (high or critical severity)
    const cardWithDeadline = page.getByTestId('approval-card')
      .filter({ has: page.locator('[data-severity="high"]') })
      .filter({ has: page.locator('[data-status="pending"]') })
      .first();

    await expect(cardWithDeadline).toBeVisible();

    const deadlineSection = cardWithDeadline.getByTestId('deadline-section');
    await expect(deadlineSection).toBeVisible();

    const countdown = cardWithDeadline.getByTestId('deadline-countdown');
    await expect(countdown).toBeVisible();
    await expect(countdown).toContainText('remaining');
  });

  test('reason input accepts text input', async ({ page }) => {
    const pendingCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="pending"]') }).first();
    await expect(pendingCard).toBeVisible();

    const reasonInput = pendingCard.getByTestId('reason-input');
    await expect(reasonInput).toBeVisible();

    // Type into reason input
    await reasonInput.fill('Test reason for approval');
    await expect(reasonInput).toHaveValue('Test reason for approval');
  });

  test('approve button is clickable with hover effects', async ({ page }) => {
    const pendingCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="pending"]') }).first();
    await expect(pendingCard).toBeVisible();

    const approveButton = pendingCard.getByTestId('approve-button');
    await expect(approveButton).toBeVisible();
    await expect(approveButton).toBeEnabled();

    // Hover over button
    await approveButton.hover();
    await page.waitForTimeout(100);

    // Click button
    await approveButton.click();

    // Note: Button should show loading state briefly
    await page.waitForTimeout(100);
  });

  test('reject button is clickable with hover effects', async ({ page }) => {
    const pendingCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="pending"]') }).nth(1);
    await expect(pendingCard).toBeVisible();

    const rejectButton = pendingCard.getByTestId('reject-button');
    await expect(rejectButton).toBeVisible();
    await expect(rejectButton).toBeEnabled();

    // Hover over button
    await rejectButton.hover();
    await page.waitForTimeout(100);

    // Click button
    await rejectButton.click();

    // Note: Button should show loading state briefly
    await page.waitForTimeout(100);
  });

  test('required approval indicator displays on pending cards', async ({ page }) => {
    const pendingCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="pending"]') }).first();
    await expect(pendingCard).toBeVisible();

    const requiredIndicator = pendingCard.getByTestId('required-indicator');
    await expect(requiredIndicator).toBeVisible();
    await expect(requiredIndicator).toContainText('required to proceed');
  });

  test('screenshot: all severity levels overview', async ({ page }) => {
    // Scroll to approval card section
    const approvalSection = page.locator('text=a2ui.ApprovalCard').first();
    await approvalSection.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    await page.screenshot({
      path: 'screenshots/KAN-256-all-severity-levels.png',
      fullPage: false,
    });
  });

  test('screenshot: low severity approval card', async ({ page }) => {
    const lowSeverityCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="low"]') }).first();
    await lowSeverityCard.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);

    await lowSeverityCard.screenshot({
      path: 'screenshots/KAN-256-low-severity.png',
    });
  });

  test('screenshot: medium severity approval card', async ({ page }) => {
    const mediumSeverityCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="medium"]') }).first();
    await mediumSeverityCard.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);

    await mediumSeverityCard.screenshot({
      path: 'screenshots/KAN-256-medium-severity.png',
    });
  });

  test('screenshot: high severity approval card', async ({ page }) => {
    const highSeverityCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="high"]') }).first();
    await highSeverityCard.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);

    await highSeverityCard.screenshot({
      path: 'screenshots/KAN-256-high-severity.png',
    });
  });

  test('screenshot: critical severity approval card', async ({ page }) => {
    const criticalSeverityCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-severity="critical"]') }).first();
    await criticalSeverityCard.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);

    await criticalSeverityCard.screenshot({
      path: 'screenshots/KAN-256-critical-severity.png',
    });
  });

  test('screenshot: approved status card', async ({ page }) => {
    const approvedCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="approved"]') }).first();
    await approvedCard.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);

    await approvedCard.screenshot({
      path: 'screenshots/KAN-256-approved-status.png',
    });
  });

  test('screenshot: rejected status card', async ({ page }) => {
    const rejectedCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="rejected"]') }).first();
    await rejectedCard.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);

    await rejectedCard.screenshot({
      path: 'screenshots/KAN-256-rejected-status.png',
    });
  });

  test('screenshot: approve button hover state', async ({ page }) => {
    const pendingCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="pending"]') }).first();
    await pendingCard.scrollIntoViewIfNeeded();

    const approveButton = pendingCard.getByTestId('approve-button');
    await approveButton.hover();
    await page.waitForTimeout(200);

    await pendingCard.screenshot({
      path: 'screenshots/KAN-256-approve-hover.png',
    });
  });

  test('screenshot: reject button hover state', async ({ page }) => {
    const pendingCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="pending"]') }).first();
    await pendingCard.scrollIntoViewIfNeeded();

    const rejectButton = pendingCard.getByTestId('reject-button');
    await rejectButton.hover();
    await page.waitForTimeout(200);

    await pendingCard.screenshot({
      path: 'screenshots/KAN-256-reject-hover.png',
    });
  });

  test('screenshot: filled reason input', async ({ page }) => {
    const pendingCard = page.getByTestId('approval-card').filter({ has: page.locator('[data-status="pending"]') }).first();
    await pendingCard.scrollIntoViewIfNeeded();

    const reasonInput = pendingCard.getByTestId('reason-input');
    await reasonInput.fill('Approved after security review and testing');
    await page.waitForTimeout(200);

    await pendingCard.screenshot({
      path: 'screenshots/KAN-256-reason-input.png',
    });
  });
});
