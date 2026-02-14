import { test, expect } from '@playwright/test';

test.describe('TestResults Component E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3010/test-results-demo');
    await page.waitForLoadState('networkidle');
  });

  test('should display all 4 status state buttons', async ({ page }) => {
    const pendingButton = page.getByRole('button', { name: 'Pending' });
    const runningButton = page.getByRole('button', { name: 'Running' });
    const passedButton = page.getByRole('button', { name: 'Passed' });
    const failedButton = page.getByRole('button', { name: 'Failed' });

    await expect(pendingButton).toBeVisible();
    await expect(runningButton).toBeVisible();
    await expect(passedButton).toBeVisible();
    await expect(failedButton).toBeVisible();
  });

  test('should display passed status by default', async ({ page }) => {
    const statusBadge = page.getByTestId('status-badge-passed');
    await expect(statusBadge).toBeVisible();
    await expect(statusBadge).toContainText('Passed');
  });

  test('should switch to pending status when clicked', async ({ page }) => {
    await page.getByRole('button', { name: 'Pending' }).click();

    const statusBadge = page.getByTestId('status-badge-pending');
    await expect(statusBadge).toBeVisible();
    await expect(statusBadge).toContainText('Pending');

    // Should show pending empty state
    await expect(page.getByTestId('pending-state')).toBeVisible();
    await expect(page.getByText('Tests are pending execution...')).toBeVisible();
  });

  test('should switch to running status and show progress', async ({ page }) => {
    await page.getByRole('button', { name: 'Running' }).click();

    const statusBadge = page.getByTestId('status-badge-running');
    await expect(statusBadge).toBeVisible();
    await expect(statusBadge).toContainText('Running');

    // Should show test summary
    await expect(page.getByTestId('total-tests')).toContainText('50');
    await expect(page.getByTestId('passed-tests')).toContainText('35');

    // Progress bar should say "Progress" not "Pass Rate"
    await expect(page.getByText('Progress')).toBeVisible();

    // Progress bar should be visible and animated
    const progressBar = page.getByTestId('progress-bar');
    await expect(progressBar).toBeVisible();
    const progressBarClass = await progressBar.getAttribute('class');
    expect(progressBarClass).toContain('animate-pulse');
  });

  test('should display passed status with test suites', async ({ page }) => {
    await page.getByRole('button', { name: 'Passed' }).click();

    // Should show test summary with 100% pass rate
    await expect(page.getByTestId('total-tests')).toContainText('120');
    await expect(page.getByTestId('passed-tests')).toContainText('120');
    await expect(page.getByText('100%')).toBeVisible();

    // Should display test suites section
    await expect(page.getByTestId('test-suites')).toBeVisible();
    await expect(page.getByText('Test Suites')).toBeVisible();

    // Should have multiple suites
    await expect(page.getByTestId('test-suite-0')).toBeVisible();
    await expect(page.getByTestId('test-suite-1')).toBeVisible();

    // Suite names should be visible
    await expect(page.getByText('Button Component')).toBeVisible();
    await expect(page.getByText('Form Component')).toBeVisible();
  });

  test('should expand and collapse test suites', async ({ page }) => {
    await page.getByRole('button', { name: 'Passed' }).click();

    // Initially suite details should not be visible
    await expect(page.getByTestId('suite-details-0')).not.toBeVisible();

    // Click on first suite to expand
    await page.getByTestId('test-suite-0').click();

    // Suite details should now be visible
    await expect(page.getByTestId('suite-details-0')).toBeVisible();
    await expect(page.getByText('Passed', { exact: true })).toBeVisible();

    // Click again to collapse
    await page.getByTestId('test-suite-0').click();
    await expect(page.getByTestId('suite-details-0')).not.toBeVisible();
  });

  test('should display failed status with mixed results', async ({ page }) => {
    await page.getByRole('button', { name: 'Failed' }).click();

    const statusBadge = page.getByTestId('status-badge-failed');
    await expect(statusBadge).toBeVisible();
    await expect(statusBadge).toContainText('Failed');

    // Should show test counts
    await expect(page.getByTestId('total-tests')).toContainText('85');
    await expect(page.getByTestId('passed-tests')).toContainText('70');
    await expect(page.getByTestId('failed-tests')).toContainText('10');
    await expect(page.getByTestId('skipped-tests')).toContainText('5');

    // Should show test suites with different statuses
    await expect(page.getByTestId('suite-status-passed-0')).toBeVisible();
    await expect(page.getByTestId('suite-status-failed-1')).toBeVisible();
    await expect(page.getByTestId('suite-status-pending-4')).toBeVisible();
  });

  test('should toggle logs visibility', async ({ page }) => {
    await page.getByRole('button', { name: 'Failed' }).click();

    // Logs section should be visible
    await expect(page.getByTestId('logs-section')).toBeVisible();

    // Initially logs content is shown (showDetails: true)
    await expect(page.getByTestId('logs-content')).toBeVisible();

    // Click Hide button
    await page.getByTestId('toggle-logs-button').click();

    // Logs content should be hidden
    await expect(page.getByTestId('logs-content')).not.toBeVisible();
    await expect(page.getByTestId('toggle-logs-button')).toContainText('Show');

    // Click Show button
    await page.getByTestId('toggle-logs-button').click();

    // Logs content should be visible again
    await expect(page.getByTestId('logs-content')).toBeVisible();
    await expect(page.getByTestId('toggle-logs-button')).toContainText('Hide');
  });

  test('should display colored log entries', async ({ page }) => {
    await page.getByRole('button', { name: 'Failed' }).click();

    // Ensure logs are visible
    const logsButton = page.getByTestId('toggle-logs-button');
    const buttonText = await logsButton.textContent();
    if (buttonText === 'Show') {
      await logsButton.click();
    }

    // Check for different log types
    await expect(page.getByText('[ERROR] Payment gateway timeout')).toBeVisible();
    await expect(page.getByText('[WARN] Slow response time detected')).toBeVisible();
    await expect(page.getByText('[INFO] Test run completed with failures')).toBeVisible();
  });

  test('should display duration information', async ({ page }) => {
    await page.getByRole('button', { name: 'Passed' }).click();

    await expect(page.getByTestId('duration')).toBeVisible();
    await expect(page.getByText('8.45s')).toBeVisible();
  });
});
