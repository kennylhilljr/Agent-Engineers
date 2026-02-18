/**
 * Playwright browser tests for File Change Summary component
 * Tests all 8 test scenarios from Linear requirements (AI-100)
 */

const { chromium } = require('playwright');
const path = require('path');

describe('File Change Summary - Browser Tests (AI-100)', () => {
    let browser;
    let page;
    const dashboardPath = path.join(__dirname, '..', 'dashboard.html');

    beforeAll(async () => {
        browser = await chromium.launch({ headless: true });
    });

    afterAll(async () => {
        await browser.close();
    });

    beforeEach(async () => {
        page = await browser.newPage();
        await page.goto(`file://${dashboardPath}`);
    });

    afterEach(async () => {
        await page.close();
    });

    // Test Step 1: Open dashboard and navigate to the Code Activity section
    test('Step 1: Should display Code Activity - File Changes section', async () => {
        // Wait for page to load
        await page.waitForSelector('.container', { timeout: 5000 });

        // Look for the File Changes card
        const fileChangesCard = await page.locator('text=Code Activity - File Changes').count();
        expect(fileChangesCard).toBeGreaterThan(0);

        // Check that the file changes container exists
        const container = await page.locator('[data-testid="file-changes-container"]').count();
        expect(container).toBe(1);
    });

    // Test Step 2: Verify file change summary displays after a coding task
    test('Step 2: Should display file change summary for coding tasks', async () => {
        // Mock file change data
        const mockData = {
            events: [
                {
                    agent_name: 'coding',
                    event_id: 'test-event-1',
                    status: 'success',
                    file_changes: [
                        {
                            path: 'src/components/Dashboard.tsx',
                            change_type: 'created',
                            lines_added: 150,
                            lines_removed: 0,
                            language: 'typescript',
                            diff: '+import React from "react";\n+export const Dashboard = () => {\n+  return <div>Dashboard</div>;\n+};'
                        },
                        {
                            path: 'src/styles/main.css',
                            change_type: 'modified',
                            lines_added: 25,
                            lines_removed: 10,
                            language: 'css',
                            diff: '-.old-class { color: red; }\n+.new-class { color: blue; }'
                        }
                    ]
                }
            ],
            agents: {}
        };

        // Inject the render function call
        await page.evaluate((data) => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(data.events);
            }
        }, mockData);

        // Wait for rendering
        await page.waitForTimeout(500);

        // Verify file change items are displayed
        const fileItems = await page.locator('[data-testid="file-change-item"]').count();
        expect(fileItems).toBe(2);
    });

    // Test Step 3: Check that files are categorized (Created/Modified/Deleted)
    test('Step 3: Should categorize files correctly', async () => {
        const mockData = {
            events: [
                {
                    agent_name: 'coding',
                    file_changes: [
                        { path: 'new.js', change_type: 'created', lines_added: 50, lines_removed: 0, language: 'javascript', diff: '+console.log("new");' },
                        { path: 'mod.js', change_type: 'modified', lines_added: 10, lines_removed: 5, language: 'javascript', diff: '-old\n+new' },
                        { path: 'del.js', change_type: 'deleted', lines_added: 0, lines_removed: 30, language: 'javascript', diff: '-deleted' }
                    ]
                }
            ]
        };

        await page.evaluate((data) => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(data.events);
            }
        }, mockData);

        await page.waitForTimeout(500);

        // Check counts
        const createdCount = await page.locator('[data-testid="files-created-count"]').textContent();
        const modifiedCount = await page.locator('[data-testid="files-modified-count"]').textContent();
        const deletedCount = await page.locator('[data-testid="files-deleted-count"]').textContent();

        expect(createdCount).toBe('1');
        expect(modifiedCount).toBe('1');
        expect(deletedCount).toBe('1');
    });

    // Test Step 4: Verify line counts show (added/removed lines)
    test('Step 4: Should display line counts correctly', async () => {
        const mockData = {
            events: [
                {
                    agent_name: 'coding',
                    file_changes: [
                        { path: 'file1.js', change_type: 'created', lines_added: 100, lines_removed: 0, language: 'javascript', diff: '' },
                        { path: 'file2.js', change_type: 'modified', lines_added: 25, lines_removed: 15, language: 'javascript', diff: '' }
                    ]
                }
            ]
        };

        await page.evaluate((data) => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(data.events);
            }
        }, mockData);

        await page.waitForTimeout(500);

        // Check total line counts
        const linesAdded = await page.locator('[data-testid="total-lines-added"]').textContent();
        const linesRemoved = await page.locator('[data-testid="total-lines-removed"]').textContent();

        expect(linesAdded).toBe('+125');
        expect(linesRemoved).toBe('-15');
    });

    // Test Step 5: Test collapsible diff view for each file
    test('Step 5: Should expand and collapse diff view', async () => {
        const mockData = {
            events: [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'test.js',
                            change_type: 'modified',
                            lines_added: 5,
                            lines_removed: 2,
                            language: 'javascript',
                            diff: '@@ -1,3 +1,6 @@\n-old line\n+new line 1\n+new line 2'
                        }
                    ]
                }
            ]
        };

        await page.evaluate((data) => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(data.events);
            }
        }, mockData);

        await page.waitForTimeout(500);

        // Check initial state - should be collapsed
        const diffContent = page.locator('[data-testid="file-diff-content"]').first();
        let isExpanded = await diffContent.evaluate(el => el.classList.contains('expanded'));
        expect(isExpanded).toBe(false);

        // Click to expand
        const fileHeader = page.locator('.file-change-header').first();
        await fileHeader.click();
        await page.waitForTimeout(300);

        isExpanded = await diffContent.evaluate(el => el.classList.contains('expanded'));
        expect(isExpanded).toBe(true);

        // Click to collapse
        await fileHeader.click();
        await page.waitForTimeout(300);

        isExpanded = await diffContent.evaluate(el => el.classList.contains('expanded'));
        expect(isExpanded).toBe(false);
    });

    // Test Step 6: Verify syntax highlighting in diff view
    test('Step 6: Should display diff with syntax highlighting', async () => {
        const mockData = {
            events: [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'app.js',
                            change_type: 'modified',
                            lines_added: 3,
                            lines_removed: 2,
                            language: 'javascript',
                            diff: '@@ -1,5 +1,6 @@\n-function oldFunc() {\n-  return false;\n-}\n+function newFunc() {\n+  return true;\n+}\n+console.log("test");'
                        }
                    ]
                }
            ]
        };

        await page.evaluate((data) => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(data.events);
            }
        }, mockData);

        await page.waitForTimeout(500);

        // Expand diff
        await page.locator('.file-change-header').first().click();
        await page.waitForTimeout(300);

        // Check for diff viewer and styled lines
        const diffViewer = await page.locator('.diff-viewer').count();
        expect(diffViewer).toBe(1);

        // Check for different line types
        const addedLines = await page.locator('.diff-line.added').count();
        const removedLines = await page.locator('.diff-line.removed').count();

        expect(addedLines).toBeGreaterThan(0);
        expect(removedLines).toBeGreaterThan(0);
    });

    // Test Step 7: Test with multiple file types (JS, CSS, HTML, etc.)
    test('Step 7: Should handle multiple file types', async () => {
        const mockData = {
            events: [
                {
                    agent_name: 'coding',
                    file_changes: [
                        { path: 'script.js', change_type: 'created', lines_added: 50, lines_removed: 0, language: 'javascript', diff: '+// JavaScript' },
                        { path: 'style.css', change_type: 'modified', lines_added: 20, lines_removed: 5, language: 'css', diff: '+.class { }' },
                        { path: 'index.html', change_type: 'modified', lines_added: 10, lines_removed: 2, language: 'html', diff: '+<div></div>' },
                        { path: 'app.tsx', change_type: 'created', lines_added: 100, lines_removed: 0, language: 'typescript', diff: '+const App = () => {};' },
                        { path: 'README.md', change_type: 'modified', lines_added: 5, lines_removed: 1, language: 'markdown', diff: '+# Title' }
                    ]
                }
            ]
        };

        await page.evaluate((data) => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(data.events);
            }
        }, mockData);

        await page.waitForTimeout(500);

        // Verify all file types are displayed
        const fileItems = await page.locator('[data-testid="file-change-item"]').count();
        expect(fileItems).toBe(5);

        // Check file paths
        const filePaths = await page.locator('[data-testid="file-path"]').allTextContents();
        expect(filePaths).toContain('script.js');
        expect(filePaths).toContain('style.css');
        expect(filePaths).toContain('index.html');
        expect(filePaths).toContain('app.tsx');
        expect(filePaths).toContain('README.md');
    });

    // Test Step 8: Verify empty state when no file changes
    test('Step 8: Should display empty state correctly', async () => {
        const mockData = {
            events: []
        };

        await page.evaluate((data) => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(data.events);
            }
        }, mockData);

        await page.waitForTimeout(500);

        // Check for empty state
        const emptyState = await page.locator('[data-testid="file-changes-empty"]').count();
        expect(emptyState).toBe(1);

        const emptyText = await page.locator('[data-testid="file-changes-empty"]').textContent();
        expect(emptyText).toContain('No file changes yet');
    });

    // Additional test: Visual regression check
    test('Visual: Should render with proper styling', async () => {
        const mockData = {
            events: [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'src/app.js',
                            change_type: 'modified',
                            lines_added: 15,
                            lines_removed: 8,
                            language: 'javascript',
                            diff: '@@ -1,3 +1,4 @@\n-old code\n+new code\n+another line'
                        }
                    ]
                }
            ]
        };

        await page.evaluate((data) => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(data.events);
            }
        }, mockData);

        await page.waitForTimeout(500);

        // Check that elements have proper CSS classes
        const fileChangeItem = page.locator('[data-testid="file-change-item"]').first();
        const hasProperClass = await fileChangeItem.evaluate(el => el.classList.contains('file-change-item'));
        expect(hasProperClass).toBe(true);

        // Check color coding for change types
        const modifiedBadge = page.locator('.file-change-type-badge.modified').first();
        const badgeExists = await modifiedBadge.count();
        expect(badgeExists).toBe(1);
    });

    // Performance test
    test('Performance: Should render large file lists efficiently', async () => {
        // Generate 20 file changes
        const fileChanges = Array.from({ length: 20 }, (_, i) => ({
            path: `src/file${i}.js`,
            change_type: i % 3 === 0 ? 'created' : i % 3 === 1 ? 'modified' : 'deleted',
            lines_added: Math.floor(Math.random() * 100),
            lines_removed: Math.floor(Math.random() * 50),
            language: 'javascript',
            diff: `+line ${i}`
        }));

        const mockData = {
            events: [
                {
                    agent_name: 'coding',
                    file_changes: fileChanges
                }
            ]
        };

        const startTime = Date.now();

        await page.evaluate((data) => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(data.events);
            }
        }, mockData);

        await page.waitForTimeout(500);

        const endTime = Date.now();
        const renderTime = endTime - startTime;

        // Should render in less than 2 seconds
        expect(renderTime).toBeLessThan(2000);

        // Verify all items rendered
        const fileItems = await page.locator('[data-testid="file-change-item"]').count();
        expect(fileItems).toBe(20);
    });
});
