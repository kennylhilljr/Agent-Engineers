/**
 * Standalone Screenshot Test for File Change Summary
 */

const { test } = require('@playwright/test');
const path = require('path');

const TEST_PAGE_URL = path.resolve(__dirname, '../../dashboard/test_file_changes.html');

test('Take screenshot of file change summary', async ({ page }) => {
    // Navigate to test page
    await page.goto(`file://${TEST_PAGE_URL}`);
    await page.waitForLoadState('networkidle');

    // Trigger file changes
    await page.click('[data-testid="trigger-file-changes"]');
    await page.waitForTimeout(2000);

    // Expand first file
    const fileHeader = await page.locator(`[data-testid="file-header-file-src-components-Dashboard-tsx"]`);
    await fileHeader.click();
    await page.waitForTimeout(500);

    // Take full page screenshot
    await page.screenshot({
        path: 'test-results/file-change-summary-full-page.png',
        fullPage: true
    });

    // Take screenshot of just the summary
    const summary = await page.locator('[data-testid="file-change-summary"]');
    await summary.screenshot({
        path: 'test-results/file-change-summary-component.png'
    });

    console.log('Screenshots saved to test-results/');
});
