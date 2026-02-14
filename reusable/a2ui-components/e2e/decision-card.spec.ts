import { test, expect } from '@playwright/test';

// Override base URL to use existing dev server on port 3010
test.use({ baseURL: 'http://localhost:3010' });

test.describe('DecisionCard Component E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the A2UI demo page where DecisionCard component is rendered
    await page.goto('/a2ui-demo');
    await page.waitForLoadState('networkidle');
  });

  test('multiple decision cards display with different statuses', async ({ page }) => {
    // Look for multiple DecisionCard components
    const decisionCards = page.getByTestId('decision-card');
    const count = await decisionCards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('pending decision card displays with all interactive elements', async ({ page }) => {
    const pendingCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="pending"]') }).first();
    await expect(pendingCard).toBeVisible();

    // Check question is displayed
    await expect(pendingCard.getByTestId('decision-question')).toBeVisible();

    // Check status badge
    const statusBadge = pendingCard.getByTestId('status-badge');
    await expect(statusBadge).toContainText('Pending Decision');

    // Check options section exists
    await expect(pendingCard.getByTestId('options-section')).toBeVisible();

    // Check submit button exists
    await expect(pendingCard.getByTestId('submit-button')).toBeVisible();
  });

  test('decided status card displays selected option', async ({ page }) => {
    const decidedCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="decided"]') }).first();
    await expect(decidedCard).toBeVisible();

    const statusBadge = decidedCard.getByTestId('status-badge');
    await expect(statusBadge).toContainText('Decided');

    // Check selected decision display
    await expect(decidedCard.getByTestId('selected-decision')).toBeVisible();
    await expect(decidedCard.getByTestId('decided-option-label')).toBeVisible();

    // Options section should not be visible in decided state
    await expect(decidedCard.getByTestId('options-section')).not.toBeVisible();
  });

  test('cancelled status card displays correctly', async ({ page }) => {
    const cancelledCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="cancelled"]') }).first();
    await expect(cancelledCard).toBeVisible();

    const statusBadge = cancelledCard.getByTestId('status-badge');
    await expect(statusBadge).toContainText('Cancelled');

    // Check status message
    const statusMessage = cancelledCard.getByTestId('status-message');
    await expect(statusMessage).toContainText('Decision was cancelled');
  });

  test('recommendation section displays when provided', async ({ page }) => {
    const pendingCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="pending"]') }).first();

    const recommendationSection = pendingCard.getByTestId('recommendation-section');
    await expect(recommendationSection).toBeVisible();
    await expect(recommendationSection.getByTestId('recommendation-icon')).toBeVisible();
    await expect(recommendationSection.getByTestId('recommendation-text')).toBeVisible();
  });

  test('context section displays when provided', async ({ page }) => {
    const pendingCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="pending"]') }).first();

    const contextSection = pendingCard.getByTestId('context-section');
    await expect(contextSection).toBeVisible();
    await expect(contextSection.getByTestId('context-text')).toBeVisible();
  });

  test('user can select an option', async ({ page }) => {
    const pendingCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="pending"]') }).first();

    // Find an option button
    const option = pendingCard.getByTestId('option-postgres');
    await expect(option).toBeVisible();

    // Check it's not selected initially
    const isSelected = await option.getAttribute('data-selected');
    expect(isSelected).toBe('false');

    // Click to select
    await option.click();

    // Verify it's now selected
    const isNowSelected = await option.getAttribute('data-selected');
    expect(isNowSelected).toBe('true');

    // Verify selected icon appears
    await expect(pendingCard.getByTestId('selected-icon-postgres')).toBeVisible();
  });

  test('submit button is disabled when no option selected', async ({ page }) => {
    // Find a pending card with no pre-selection
    const pendingCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="pending"]') }).first();

    // First, ensure no option is selected by looking at button state
    const submitButton = pendingCard.getByTestId('submit-button');

    // Submit button should be disabled initially
    await expect(submitButton).toBeDisabled();
  });

  test('submit button enables after selecting an option', async ({ page }) => {
    const pendingCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="pending"]') }).first();

    const submitButton = pendingCard.getByTestId('submit-button');
    const option = pendingCard.getByTestId('option-postgres');

    // Select an option
    await option.click();

    // Wait a moment for state update
    await page.waitForTimeout(100);

    // Submit button should now be enabled
    await expect(submitButton).toBeEnabled();
  });

  test('recommended badge displays on recommended option', async ({ page }) => {
    const pendingCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="pending"]') }).first();

    // Check that the recommended option has a badge
    const postgresOption = pendingCard.getByTestId('option-postgres');
    await expect(postgresOption).toBeVisible();

    // Verify the recommended badge exists
    const recommendedBadge = pendingCard.getByTestId('recommended-badge-postgres');
    await expect(recommendedBadge).toBeVisible();
    await expect(recommendedBadge).toContainText('Recommended');
  });

  test('reasoning input displays when reasoningVisible is true', async ({ page }) => {
    const pendingCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="pending"]') }).first();

    const reasoningSection = pendingCard.getByTestId('reasoning-section');
    await expect(reasoningSection).toBeVisible();

    const reasoningInput = pendingCard.getByTestId('reasoning-input');
    await expect(reasoningInput).toBeVisible();

    // Test typing in reasoning input
    await reasoningInput.fill('This is my reasoning for the choice');
    await expect(reasoningInput).toHaveValue('This is my reasoning for the choice');
  });

  test('status icon displays for each status', async ({ page }) => {
    // Check pending status icon
    const pendingCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="pending"]') }).first();
    await expect(pendingCard.getByTestId('status-icon')).toBeVisible();

    // Check decided status icon
    const decidedCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="decided"]') }).first();
    await expect(decidedCard.getByTestId('status-icon')).toBeVisible();

    // Check cancelled status icon
    const cancelledCard = page.getByTestId('decision-card').filter({ has: page.locator('[data-status="cancelled"]') }).first();
    await expect(cancelledCard.getByTestId('status-icon')).toBeVisible();
  });
});
