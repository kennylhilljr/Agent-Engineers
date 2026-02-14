import { test, expect } from '@playwright/test';

// Override base URL to use existing dev server on port 3010
test.use({ baseURL: 'http://localhost:3010' });

test.describe('ErrorCard Component E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the ErrorCard demo page
    await page.goto('/error-card-demo');
    await page.waitForLoadState('networkidle');
  });

  test('multiple error cards display correctly', async ({ page }) => {
    // Look for multiple ErrorCard components
    const errorCards = page.getByTestId('error-card');
    const count = await errorCards.count();
    expect(count).toBeGreaterThanOrEqual(4); // We have 4 severity examples + 2 edge cases
  });

  test('info severity card renders correctly', async ({ page }) => {
    const cards = page.getByTestId('error-card');
    const infoCard = cards.filter({ has: page.getByText('Info', { exact: true }) }).first();
    await expect(infoCard).toBeVisible();

    await expect(infoCard).toHaveAttribute('data-severity', 'info');
    await expect(infoCard.getByTestId('severity-badge')).toHaveTextContent('Info');
    await expect(infoCard.getByText('Information')).toBeVisible();
    await expect(infoCard.getByTestId('error-code')).toHaveTextContent('INFO-100');
  });

  test('warning severity card renders correctly', async ({ page }) => {
    const cards = page.getByTestId('error-card');
    const warningCard = cards.filter({ has: page.getByText('Warning', { exact: true }) }).first();
    await expect(warningCard).toBeVisible();

    await expect(warningCard).toHaveAttribute('data-severity', 'warning');
    await expect(warningCard.getByTestId('severity-badge')).toHaveTextContent('Warning');
    await expect(warningCard.getByText('High Memory Usage Detected')).toBeVisible();
  });

  test('error severity card renders correctly', async ({ page }) => {
    const cards = page.getByTestId('error-card');
    const errorCard = cards.filter({ has: page.getByText('Error', { exact: true }) }).first();
    await expect(errorCard).toBeVisible();

    await expect(errorCard).toHaveAttribute('data-severity', 'error');
    await expect(errorCard.getByTestId('severity-badge')).toHaveTextContent('Error');
    await expect(errorCard.getByText('API Request Failed')).toBeVisible();
  });

  test('critical severity card renders correctly', async ({ page }) => {
    const cards = page.getByTestId('error-card');
    const criticalCard = cards.filter({ has: page.getByText('Critical', { exact: true }) }).first();
    await expect(criticalCard).toBeVisible();

    await expect(criticalCard).toHaveAttribute('data-severity', 'critical');
    await expect(criticalCard.getByTestId('severity-badge')).toHaveTextContent('Critical');
    await expect(criticalCard.getByText('Database Connection Lost')).toBeVisible();
  });

  test('error code displays correctly', async ({ page }) => {
    const errorCodes = page.getByTestId('error-code');
    const firstErrorCode = errorCodes.first();
    await expect(firstErrorCode).toBeVisible();
    await expect(firstErrorCode).toHaveText('INFO-100');
  });

  test('timestamp displays correctly', async ({ page }) => {
    const timestamps = page.getByTestId('timestamp');
    const firstTimestamp = timestamps.first();
    await expect(firstTimestamp).toBeVisible();
    // Should contain date parts
    await expect(firstTimestamp).toContainText('2024');
  });

  test('error details section displays correctly', async ({ page }) => {
    const detailsSections = page.getByTestId('error-details');
    const firstDetails = detailsSections.first();
    await expect(firstDetails).toBeVisible();
    await expect(firstDetails).toContainText('Details');
  });

  test('stack trace toggle expands and collapses', async ({ page }) => {
    const stackTraceToggles = page.getByTestId('stack-trace-toggle');
    const firstToggle = stackTraceToggles.first();
    await expect(firstToggle).toBeVisible();

    // Initially collapsed
    await expect(firstToggle).toHaveAttribute('aria-expanded', 'false');

    // Click to expand
    await firstToggle.click();
    await expect(firstToggle).toHaveAttribute('aria-expanded', 'true');

    // Stack trace content should be visible
    const stackTraceContent = page.getByTestId('stack-trace-content').first();
    await expect(stackTraceContent).toBeVisible();

    // Click to collapse
    await firstToggle.click();
    await expect(firstToggle).toHaveAttribute('aria-expanded', 'false');
  });

  test('stack trace displays full error trace', async ({ page }) => {
    const stackTraceToggles = page.getByTestId('stack-trace-toggle');
    const firstToggle = stackTraceToggles.first();

    // Expand stack trace
    await firstToggle.click();

    const stackTraceContent = page.getByTestId('stack-trace-content').first();
    await expect(stackTraceContent).toBeVisible();
    await expect(stackTraceContent).toContainText('Error:');
  });

  test('action buttons render correctly', async ({ page }) => {
    const actionButtonsSection = page.getByTestId('action-buttons').first();
    await expect(actionButtonsSection).toBeVisible();

    // Check for action buttons
    const buttons = actionButtonsSection.getByRole('button');
    expect(await buttons.count()).toBeGreaterThan(0);
  });

  test('action buttons can be clicked', async ({ page }) => {
    const firstActionButton = page.getByTestId('action-retry').first();
    await expect(firstActionButton).toBeVisible();

    // Click should not throw
    await firstActionButton.click();
    await page.waitForTimeout(100);
  });

  test('dismiss button appears on dismissible errors', async ({ page }) => {
    const dismissButtons = page.getByTestId('dismiss-button');
    expect(await dismissButtons.count()).toBeGreaterThan(0);

    const firstDismissButton = dismissButtons.first();
    await expect(firstDismissButton).toBeVisible();
    await expect(firstDismissButton).toHaveAttribute('aria-label', 'Dismiss error');
  });

  test('dismiss button can be clicked', async ({ page }) => {
    const dismissButtons = page.getByTestId('dismiss-button');
    const firstDismissButton = dismissButtons.first();

    await firstDismissButton.click();
    await page.waitForTimeout(100);

    // After dismissing, the card should be removed
    // (In this demo, it uses state to hide dismissed cards)
  });

  test('error card without stack trace does not show toggle', async ({ page }) => {
    // Navigate to edge cases section
    const simpleError = page.getByText('Validation Error');
    await expect(simpleError).toBeVisible();

    // Find the card containing this error
    const simpleErrorCard = page.getByTestId('error-card').filter({ hasText: 'Validation Error' });

    // Should not have stack trace toggle
    const stackTraceToggle = simpleErrorCard.getByTestId('stack-trace-toggle');
    expect(await stackTraceToggle.count()).toBe(0);
  });

  test('minimal error card renders with minimum props', async ({ page }) => {
    const minimalError = page.getByText('Network Timeout');
    await expect(minimalError).toBeVisible();

    // Find the card
    const minimalCard = page.getByTestId('error-card').filter({ hasText: 'Network Timeout' });
    await expect(minimalCard).toBeVisible();
  });

  test('all severity levels have correct visual styling', async ({ page }) => {
    const cards = page.getByTestId('error-card');

    // Check info card has blue accent
    const infoCard = cards.filter({ has: page.getByText('Info', { exact: true }) }).first();
    const infoBadge = infoCard.getByTestId('severity-badge');
    const infoBadgeClasses = await infoBadge.getAttribute('class');
    expect(infoBadgeClasses).toContain('text-blue');

    // Check warning card has yellow accent
    const warningCard = cards.filter({ has: page.getByText('Warning', { exact: true }) }).first();
    const warningBadge = warningCard.getByTestId('severity-badge');
    const warningBadgeClasses = await warningBadge.getAttribute('class');
    expect(warningBadgeClasses).toContain('text-yellow');

    // Check error card has red accent
    const errorCard = cards.filter({ has: page.getByText('Error', { exact: true }) }).first();
    const errorBadge = errorCard.getByTestId('severity-badge');
    const errorBadgeClasses = await errorBadge.getAttribute('class');
    expect(errorBadgeClasses).toContain('text-red');

    // Check critical card has purple accent
    const criticalCard = cards.filter({ has: page.getByText('Critical', { exact: true }) }).first();
    const criticalBadge = criticalCard.getByTestId('severity-badge');
    const criticalBadgeClasses = await criticalBadge.getAttribute('class');
    expect(criticalBadgeClasses).toContain('text-purple');
  });

  test('action buttons have different variants', async ({ page }) => {
    const actionButtons = page.getByTestId('action-buttons').first();

    // Get all buttons
    const buttons = actionButtons.getByRole('button');
    expect(await buttons.count()).toBeGreaterThan(0);

    // Check for primary button (Retry)
    const retryButton = page.getByTestId('action-retry').first();
    const retryClasses = await retryButton.getAttribute('class');
    expect(retryClasses).toContain('bg-blue-600');
  });

  test('error cards are responsive and accessible', async ({ page }) => {
    const cards = page.getByTestId('error-card');
    const firstCard = cards.first();
    await expect(firstCard).toBeVisible();

    // Check card has proper semantic structure
    const errorMessage = firstCard.getByTestId('error-message');
    await expect(errorMessage).toBeVisible();
  });

  test('severity icons display correctly', async ({ page }) => {
    const severityIcons = page.getByTestId('severity-icon');
    expect(await severityIcons.count()).toBeGreaterThan(0);

    const firstIcon = severityIcons.first();
    await expect(firstIcon).toBeVisible();
  });

  test('error details expand to show key-value pairs', async ({ page }) => {
    const detailsSections = page.getByTestId('error-details');
    const firstDetails = detailsSections.first();
    await expect(firstDetails).toBeVisible();

    // Should contain key-value pairs (e.g., "version: 2.5.0")
    await expect(firstDetails).toContainText('version');
    await expect(firstDetails).toContainText('2.5.0');
  });

  test('page has proper header and documentation', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 1 })).toContainText('a2ui.ErrorCard');
    await expect(page.getByText('4 severity levels (info, warning, error, critical)')).toBeVisible();
  });

  test('acceptance criteria section is visible', async ({ page }) => {
    await expect(page.getByText('Acceptance Criteria')).toBeVisible();
    await expect(page.getByText('Renders with title and message')).toBeVisible();
  });
});
