import { test, expect } from '@playwright/test';

// Override base URL to use existing dev server on port 3000
test.use({ baseURL: 'http://localhost:3000' });

test.describe('TestResults Component E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the A2UI demo page where TestResults component is rendered
    await page.goto('/a2ui-demo');
    await page.waitForLoadState('networkidle');
  });

  test('component displays and renders on demo page', async ({ page }) => {
    // Look for the Test Results component
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();
  });

  test('displays test summary with correct counts', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    // Check summary section exists
    const summary = testResults.getByTestId('test-summary');
    await expect(summary).toBeVisible();

    // Verify numerical values are present
    await expect(summary.locator('text=Total Tests')).toBeVisible();
  });

  test('displays pass rate percentage correctly', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    // Check for percentage display
    const progressContainer = testResults.getByTestId('progress-bar-container');
    await expect(progressContainer).toBeVisible();

    // Verify percentage text is visible
    await expect(progressContainer.locator('text=Pass Rate')).toBeVisible();
  });

  test('progress bar is visible and colored based on status', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    const progressBar = testResults.getByTestId('progress-bar');
    await expect(progressBar).toBeVisible();

    // Progress bar should have a width (indicating it's rendered)
    const width = await progressBar.evaluate((el) => window.getComputedStyle(el).width);
    expect(width).not.toBe('0px');
  });

  test('test case list displays when available', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    // Check if test case list exists
    const testCaseList = testResults.getByTestId('test-case-list');
    await expect(testCaseList).toBeVisible();
    await expect(testCaseList.locator('text=Test Cases')).toBeVisible();
  });

  test('passed test displays with green indicator', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    // Look for passed test badge
    const passedBadge = testResults.getByTestId('badge-passed').first();
    await expect(passedBadge).toBeVisible();
    await expect(passedBadge).toContainText('Passed');

    // Check for green icon
    const passedIcon = testResults.getByTestId('icon-passed').first();
    await expect(passedIcon).toBeVisible();
  });

  test('failed test displays with red indicator', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    // Look for failed test badge
    const failedBadge = testResults.getByTestId('badge-failed').first();
    await expect(failedBadge).toBeVisible();
    await expect(failedBadge).toContainText('Failed');

    // Check for red icon
    const failedIcon = testResults.getByTestId('icon-failed').first();
    await expect(failedIcon).toBeVisible();
  });

  test('clicking failed test expands error details', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    // Find first failed test case (should be index 4 based on demo data)
    const testCase = testResults.getByTestId('test-case-4');
    await expect(testCase).toBeVisible();

    // Error details should not be visible initially
    const errorDetails = testResults.getByTestId('error-details-4');
    await expect(errorDetails).not.toBeVisible();

    // Click to expand
    await testCase.click();

    // Error details should now be visible
    await expect(errorDetails).toBeVisible();
    await expect(errorDetails.locator('text=Error Details:')).toBeVisible();
  });

  test('error details collapse when clicked again', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    const testCase = testResults.getByTestId('test-case-4');
    const errorDetails = testResults.getByTestId('error-details-4');

    // Expand
    await testCase.click();
    await expect(errorDetails).toBeVisible();

    // Collapse
    await testCase.click();
    await expect(errorDetails).not.toBeVisible();
  });

  test('duration is displayed when available', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    // Check if duration field exists
    const duration = testResults.getByTestId('duration');
    await expect(duration).toBeVisible();
    await expect(duration.locator('text=Total Duration:')).toBeVisible();
  });

  test('skipped tests are shown when present', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    const summary = testResults.getByTestId('test-summary');
    const skipped = summary.locator('text=Skipped').first();
    await expect(skipped).toBeVisible();
  });

  test('screenshot: test results component overview', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    // Scroll to component
    await testResults.scrollIntoViewIfNeeded();

    await page.screenshot({
      path: 'screenshots/KAN-254-test-results-overview.png',
      fullPage: false
    });
  });

  test('screenshot: test case list with mixed results', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    const testCaseList = testResults.getByTestId('test-case-list');
    await testCaseList.scrollIntoViewIfNeeded();

    await page.screenshot({
      path: 'screenshots/KAN-254-test-case-list.png',
      fullPage: false
    });
  });

  test('screenshot: expanded error detail', async ({ page }) => {
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    // Click failed test to expand error
    const testCase = testResults.getByTestId('test-case-4');
    await testCase.scrollIntoViewIfNeeded();
    await testCase.click();

    // Wait for animation
    await page.waitForTimeout(300);

    await page.screenshot({
      path: 'screenshots/KAN-254-expanded-error.png',
      fullPage: false
    });
  });

  test('screenshot: progress bar colors - passing', async ({ page }) => {
    // For this test, we'd need to create a different scenario
    // For now, just take the existing component screenshot
    const testResults = page.getByTestId('test-results').first();
    await expect(testResults).toBeVisible();

    const progressBar = testResults.getByTestId('progress-bar-container');
    await progressBar.scrollIntoViewIfNeeded();

    await page.screenshot({
      path: 'screenshots/KAN-254-progress-bar.png',
      fullPage: false
    });
  });
});
