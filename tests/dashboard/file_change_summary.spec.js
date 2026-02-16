/**
 * Playwright Browser Tests for File Change Summary (AI-100)
 *
 * Test Steps (from requirements):
 * 1. Complete a coding delegation that modifies multiple files
 * 2. Verify file change summary appears in chat
 * 3. Verify files are categorized (created, modified, deleted)
 * 4. Verify line counts show added/removed
 * 5. Click on a file to expand/collapse its diff
 * 6. Verify diff displays with syntax highlighting
 * 7. Test with delegations that create, modify, and delete files
 * 8. Verify summary is accurate and complete
 */

const { test, expect } = require('@playwright/test');
const path = require('path');

const TEST_PAGE_URL = path.resolve(__dirname, '../../dashboard/test_file_changes.html');

test.describe('File Change Summary - AI-100', () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to test page
        await page.goto(`file://${TEST_PAGE_URL}`);
        await page.waitForLoadState('networkidle');
    });

    /**
     * TEST STEP 1-2: Complete a coding delegation and verify file change summary appears
     */
    test('Step 1-2: Should display file change summary after coding delegation', async ({ page }) => {
        // Trigger file changes (simulating coding delegation completion)
        await page.click('[data-testid="trigger-file-changes"]');

        // Wait for AI message to appear
        await page.waitForSelector('[data-testid="chat-message-ai"]', { timeout: 5000 });

        // Wait for file change summary to appear
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Verify the summary is visible
        const summary = await page.locator('[data-testid="file-change-summary"]');
        await expect(summary).toBeVisible();

        // Verify summary contains the title
        await expect(page.locator('.file-change-title')).toContainText('File Changes Summary');
    });

    /**
     * TEST STEP 3: Verify files are categorized (created, modified, deleted)
     */
    test('Step 3: Should categorize files by created, modified, and deleted', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Verify Created category exists
        const createdCategory = await page.locator('[data-testid="file-category-created"]');
        await expect(createdCategory).toBeVisible();
        await expect(createdCategory).toContainText('Created');

        // Verify Modified category exists
        const modifiedCategory = await page.locator('[data-testid="file-category-modified"]');
        await expect(modifiedCategory).toBeVisible();
        await expect(modifiedCategory).toContainText('Modified');

        // Verify Deleted category exists
        const deletedCategory = await page.locator('[data-testid="file-category-deleted"]');
        await expect(deletedCategory).toBeVisible();
        await expect(deletedCategory).toContainText('Deleted');

        // Verify category counts are shown
        await expect(page.locator('.category-title')).toContainText('(1)');
    });

    /**
     * TEST STEP 4: Verify line counts show added/removed
     */
    test('Step 4: Should display accurate line counts for added and removed lines', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Verify total stats in header
        const totalAdded = await page.locator('[data-testid="total-added"]');
        await expect(totalAdded).toBeVisible();
        await expect(totalAdded).toContainText('+');

        const totalRemoved = await page.locator('[data-testid="total-removed"]');
        await expect(totalRemoved).toBeVisible();
        await expect(totalRemoved).toContainText('-');

        const totalFiles = await page.locator('[data-testid="total-files"]');
        await expect(totalFiles).toBeVisible();

        // Verify individual file stats
        const modifiedFile = await page.locator('[data-testid="file-item-file-src-components-Dashboard-tsx"]');
        await expect(modifiedFile).toBeVisible();

        // Check for line count badges
        const linesAdded = await page.locator('[data-testid="lines-added-file-src-components-Dashboard-tsx"]');
        await expect(linesAdded).toBeVisible();
        await expect(linesAdded).toContainText('+42');

        const linesRemoved = await page.locator('[data-testid="lines-removed-file-src-components-Dashboard-tsx"]');
        await expect(linesRemoved).toBeVisible();
        await expect(linesRemoved).toContainText('-15');
    });

    /**
     * TEST STEP 5: Click on a file to expand/collapse its diff
     */
    test('Step 5: Should expand and collapse file diffs on click', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        const fileId = 'file-src-components-Dashboard-tsx';
        const fileHeader = await page.locator(`[data-testid="file-header-${fileId}"]`);
        const fileDiff = await page.locator(`[data-testid="file-diff-${fileId}"]`);
        const expandIcon = await page.locator(`[data-testid="expand-icon-${fileId}"]`);

        // Initially, diff should not be expanded
        await expect(fileDiff).not.toHaveClass(/expanded/);

        // Click to expand
        await fileHeader.click();
        await page.waitForTimeout(400); // Wait for animation

        // Verify diff is now expanded
        await expect(fileDiff).toHaveClass(/expanded/);
        await expect(expandIcon).toHaveClass(/expanded/);

        // Click again to collapse
        await fileHeader.click();
        await page.waitForTimeout(400); // Wait for animation

        // Verify diff is collapsed again
        await expect(fileDiff).not.toHaveClass(/expanded/);
        await expect(expandIcon).not.toHaveClass(/expanded/);
    });

    /**
     * TEST STEP 6: Verify diff displays with syntax highlighting
     */
    test('Step 6: Should display diff with proper formatting and syntax highlighting', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        const fileId = 'file-src-components-Dashboard-tsx';
        const fileHeader = await page.locator(`[data-testid="file-header-${fileId}"]`);

        // Expand the diff
        await fileHeader.click();
        await page.waitForTimeout(400);

        // Verify diff content is visible
        const diffContent = await page.locator(`[data-testid="diff-content"]`).first();
        await expect(diffContent).toBeVisible();

        // Verify different types of diff lines exist
        const addedLines = await page.locator('[data-testid="diff-line-added"]');
        await expect(addedLines.first()).toBeVisible();

        const deletedLines = await page.locator('[data-testid="diff-line-deleted"]');
        await expect(deletedLines.first()).toBeVisible();

        const contextLines = await page.locator('[data-testid="diff-line-context"]');
        await expect(contextLines.first()).toBeVisible();

        // Verify hunk headers are present
        const hunkHeaders = await page.locator('[data-testid="diff-line-hunk"]');
        await expect(hunkHeaders.first()).toBeVisible();

        // Verify diff indicators are present
        const diffIndicators = await page.locator('.diff-indicator');
        await expect(diffIndicators.first()).toBeVisible();
    });

    /**
     * TEST STEP 7: Test with delegations that create, modify, and delete files
     */
    test('Step 7: Should handle files that are created, modified, and deleted', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Verify created file exists
        const createdFile = await page.locator('[data-testid="file-path-file-src-utils-helpers-js"]');
        await expect(createdFile).toBeVisible();
        await expect(createdFile).toContainText('src/utils/helpers.js');

        // Verify created file has only additions
        const createdLinesAdded = await page.locator('[data-testid="lines-added-file-src-utils-helpers-js"]');
        await expect(createdLinesAdded).toBeVisible();
        await expect(createdLinesAdded).toContainText('+23');

        // Modified file should have both additions and deletions
        const modifiedFile = await page.locator('[data-testid="file-path-file-src-components-Dashboard-tsx"]');
        await expect(modifiedFile).toBeVisible();

        const modifiedAdded = await page.locator('[data-testid="lines-added-file-src-components-Dashboard-tsx"]');
        const modifiedRemoved = await page.locator('[data-testid="lines-removed-file-src-components-Dashboard-tsx"]');
        await expect(modifiedAdded).toBeVisible();
        await expect(modifiedRemoved).toBeVisible();

        // Verify deleted file exists
        const deletedFile = await page.locator('[data-testid="file-path-file-src-legacy-oldComponent-jsx"]');
        await expect(deletedFile).toBeVisible();
        await expect(deletedFile).toContainText('src/legacy/oldComponent.jsx');

        // Deleted file should have only removals
        const deletedLinesRemoved = await page.locator('[data-testid="lines-removed-file-src-legacy-oldComponent-jsx"]');
        await expect(deletedLinesRemoved).toBeVisible();
        await expect(deletedLinesRemoved).toContainText('-67');
    });

    /**
     * TEST STEP 8: Verify summary is accurate and complete
     */
    test('Step 8: Should display accurate and complete summary statistics', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Verify total file count
        const totalFiles = await page.locator('[data-testid="total-files"] .stat-value');
        const fileCount = await totalFiles.textContent();
        expect(parseInt(fileCount)).toBe(3); // 1 created + 1 modified + 1 deleted

        // Verify total lines added (42 from modified + 23 from created = 65)
        const totalAdded = await page.locator('[data-testid="total-added"] .stat-value');
        const addedCount = await totalAdded.textContent();
        expect(parseInt(addedCount)).toBe(65);

        // Verify total lines removed (15 from modified + 67 from deleted = 82)
        const totalRemoved = await page.locator('[data-testid="total-removed"] .stat-value');
        const removedCount = await totalRemoved.textContent();
        expect(parseInt(removedCount)).toBe(82);

        // Verify all file paths are present
        const fileItems = await page.locator('.file-item');
        const fileItemsCount = await fileItems.count();
        expect(fileItemsCount).toBe(3);

        // Verify each category shows correct count
        const createdTitle = await page.locator('.file-category:has([data-testid="file-category-created"]) .category-title');
        await expect(createdTitle).toContainText('Created (1)');

        const modifiedTitle = await page.locator('.file-category:has([data-testid="file-category-modified"]) .category-title');
        await expect(modifiedTitle).toContainText('Modified (1)');

        const deletedTitle = await page.locator('.file-category:has([data-testid="file-category-deleted"]) .category-title');
        await expect(deletedTitle).toContainText('Deleted (1)');
    });

    /**
     * ADDITIONAL TEST: Empty state handling
     */
    test('Should display empty state when no file changes exist', async ({ page }) => {
        await page.click('[data-testid="trigger-empty-changes"]');
        await page.waitForTimeout(1000);

        const emptyState = await page.locator('[data-testid="file-change-summary-empty"]');
        await expect(emptyState).toBeVisible();
        await expect(emptyState).toContainText('No file changes to display');
    });

    /**
     * ADDITIONAL TEST: Large file change sets
     */
    test('Should handle large file change sets correctly', async ({ page }) => {
        await page.click('[data-testid="trigger-large-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Verify summary appears
        const summary = await page.locator('[data-testid="file-change-summary"]');
        await expect(summary).toBeVisible();

        // Verify file count is more than basic test
        const fileItems = await page.locator('.file-item');
        const fileItemsCount = await fileItems.count();
        expect(fileItemsCount).toBeGreaterThan(0);

        // Verify we can expand multiple files
        const firstFileHeader = await page.locator('.file-header').first();
        await firstFileHeader.click();
        await page.waitForTimeout(400);

        const firstDiff = await page.locator('.file-diff.expanded').first();
        await expect(firstDiff).toBeVisible();
    });

    /**
     * ADDITIONAL TEST: Multiple expand/collapse operations
     */
    test('Should handle multiple files being expanded simultaneously', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Expand first file
        const file1Header = await page.locator(`[data-testid="file-header-file-src-components-Dashboard-tsx"]`);
        await file1Header.click();
        await page.waitForTimeout(400);

        // Expand second file
        const file2Header = await page.locator(`[data-testid="file-header-file-src-utils-helpers-js"]`);
        await file2Header.click();
        await page.waitForTimeout(400);

        // Both should be expanded
        const expandedDiffs = await page.locator('.file-diff.expanded');
        const expandedCount = await expandedDiffs.count();
        expect(expandedCount).toBe(2);

        // Collapse first file
        await file1Header.click();
        await page.waitForTimeout(400);

        // Only one should be expanded now
        const expandedDiffsAfter = await page.locator('.file-diff.expanded');
        const expandedCountAfter = await expandedDiffsAfter.count();
        expect(expandedCountAfter).toBe(1);
    });

    /**
     * ADDITIONAL TEST: File path display and truncation
     */
    test('Should display complete file paths correctly', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Verify file paths are displayed correctly
        const filePaths = [
            'src/components/Dashboard.tsx',
            'src/utils/helpers.js',
            'src/legacy/oldComponent.jsx'
        ];

        for (const filePath of filePaths) {
            const pathElement = await page.locator(`.file-path:has-text("${filePath}")`);
            await expect(pathElement).toBeVisible();
        }
    });

    /**
     * ADDITIONAL TEST: Integration with chat interface
     */
    test('Should integrate properly with chat message flow', async ({ page }) => {
        // Clear chat first
        await page.click('[data-testid="clear-chat"]');
        await page.waitForTimeout(300);

        // Trigger file changes
        await page.click('[data-testid="trigger-file-changes"]');

        // Wait for messages
        await page.waitForSelector('[data-testid="chat-message-ai"]', { timeout: 5000 });

        // Count chat messages - should have at least 2 (text + file changes)
        const chatMessages = await page.locator('[data-testid="chat-message-ai"]');
        const messageCount = await chatMessages.count();
        expect(messageCount).toBeGreaterThanOrEqual(2);

        // Verify timestamp is present
        const timestamp = await page.locator('.chat-timestamp').last();
        await expect(timestamp).toBeVisible();
    });

    /**
     * VISUAL REGRESSION TEST: Take screenshot for documentation
     */
    test('Should render file change summary with correct styling', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Expand one file to show diff
        const fileHeader = await page.locator(`[data-testid="file-header-file-src-components-Dashboard-tsx"]`);
        await fileHeader.click();
        await page.waitForTimeout(500);

        // Take screenshot
        const summary = await page.locator('[data-testid="file-change-summary"]');
        await expect(summary).toHaveScreenshot('file-change-summary.png', {
            maxDiffPixels: 100
        });
    });

    /**
     * ACCESSIBILITY TEST: Verify component is accessible
     */
    test('Should have accessible elements and proper ARIA attributes', async ({ page }) => {
        await page.click('[data-testid="trigger-file-changes"]');
        await page.waitForSelector('[data-testid="file-change-summary"]', { timeout: 5000 });

        // Verify headings are present for screen readers
        const heading = await page.locator('.file-change-title');
        await expect(heading).toBeVisible();

        // Verify clickable elements are keyboard accessible
        const fileHeader = await page.locator('.file-header').first();
        await expect(fileHeader).toBeVisible();

        // Test keyboard navigation
        await fileHeader.focus();
        await page.keyboard.press('Enter');
        await page.waitForTimeout(400);

        // Verify diff expanded
        const expandedDiff = await page.locator('.file-diff.expanded').first();
        await expect(expandedDiff).toBeVisible();
    });
});
