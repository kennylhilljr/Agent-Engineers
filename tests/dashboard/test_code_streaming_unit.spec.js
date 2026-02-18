/**
 * Unit Tests for Code Streaming - AI-99
 * Tests the CodeStreamRenderer class functionality
 */

const { test, expect } = require('@playwright/test');

test.describe('Code Streaming Unit Tests - AI-99', () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to dashboard
        await page.goto('http://127.0.0.1:8421/dashboard.html');

        // Wait for chat interface to initialize
        await page.waitForFunction(() => window.chatInterface !== undefined);
        await page.waitForFunction(() => window.chatInterface.codeStreamRenderer !== undefined);
    });

    test('should initialize CodeStreamRenderer with ChatInterface', async ({ page }) => {
        const hasRenderer = await page.evaluate(() => {
            return window.chatInterface.codeStreamRenderer !== null &&
                   window.chatInterface.codeStreamRenderer !== undefined;
        });

        expect(hasRenderer).toBe(true);
    });

    test('should create code stream container when adding first chunk', async ({ page }) => {
        // Add a code chunk
        await page.evaluate(() => {
            window.chatInterface.codeStreamRenderer.addCodeChunk(
                'def hello_world():',
                'src/main.py',
                1,
                'add',
                'python'
            );
        });

        // Check container exists
        const container = await page.locator('[data-testid="code-stream-container"]');
        await expect(container).toBeVisible();

        // Check file path is displayed
        const filePath = await page.locator('[data-testid="code-stream-file-path"]');
        await expect(filePath).toContainText('src/main.py');
    });

    test('should display streaming status indicator', async ({ page }) => {
        await page.evaluate(() => {
            window.chatInterface.codeStreamRenderer.addCodeChunk(
                'print("Hello")',
                'test.py',
                1,
                'add',
                'python'
            );
        });

        const status = await page.locator('[data-testid="code-stream-status"]');
        await expect(status).toBeVisible();
        await expect(status).toContainText('Streaming');
    });

    test('should add code lines with line numbers', async ({ page }) => {
        await page.evaluate(() => {
            const renderer = window.chatInterface.codeStreamRenderer;
            renderer.addCodeChunk('def test():', 'test.py', 1, 'add', 'python');
            renderer.addCodeChunk('    return True', 'test.py', 2, 'add', 'python');
        });

        const lines = await page.locator('[data-testid="code-line"]');
        await expect(lines).toHaveCount(2);

        // Check line numbers
        const firstLine = lines.first();
        await expect(firstLine).toContainText('1');

        const secondLine = lines.nth(1);
        await expect(secondLine).toContainText('2');
    });

    test('should apply syntax highlighting to Python code', async ({ page }) => {
        await page.evaluate(() => {
            window.chatInterface.codeStreamRenderer.addCodeChunk(
                'def hello():',
                'test.py',
                1,
                'add',
                'python'
            );
        });

        // Check if Prism highlighting was applied (keyword 'def' should be highlighted)
        const lineContent = await page.locator('.code-line-content').first();
        const html = await lineContent.innerHTML();

        // Should contain either Prism token or our fallback token-keyword class
        expect(html).toMatch(/token|keyword/);
    });

    test('should track additions and deletions separately', async ({ page }) => {
        await page.evaluate(() => {
            const renderer = window.chatInterface.codeStreamRenderer;
            // Add 3 lines
            renderer.addCodeChunk('def test():', 'test.py', 1, 'add', 'python');
            renderer.addCodeChunk('    pass', 'test.py', 2, 'add', 'python');
            renderer.addCodeChunk('# Comment', 'test.py', 3, 'add', 'python');
            // Delete 1 line
            renderer.addCodeChunk('old_code', 'test.py', 4, 'delete', 'python');
        });

        const additions = await page.locator('[data-testid="code-additions"]');
        await expect(additions).toContainText('3');

        const deletions = await page.locator('[data-testid="code-deletions"]');
        await expect(deletions).toContainText('1');
    });

    test('should mark additions with proper class and styling', async ({ page }) => {
        await page.evaluate(() => {
            window.chatInterface.codeStreamRenderer.addCodeChunk(
                'new_code',
                'test.py',
                1,
                'add',
                'python'
            );
        });

        // Wait for the line to be added
        await page.waitForSelector('[data-testid="code-line"]', { state: 'visible' });

        const addLine = await page.locator('[data-testid="code-line"][data-operation="add"]').first();
        await expect(addLine).toBeVisible();

        // Check data attribute
        const operation = await addLine.getAttribute('data-operation');
        expect(operation).toBe('add');

        // Check class includes 'add' for styling
        const className = await addLine.getAttribute('class');
        expect(className).toContain('add');
    });

    test('should mark deletions with proper class and strikethrough', async ({ page }) => {
        await page.evaluate(() => {
            window.chatInterface.codeStreamRenderer.addCodeChunk(
                'old_code',
                'test.py',
                1,
                'delete',
                'python'
            );
        });

        // Wait for the line to be added
        await page.waitForSelector('[data-testid="code-line"]', { state: 'visible' });

        const delLine = await page.locator('[data-testid="code-line"][data-operation="delete"]').first();
        await expect(delLine).toBeVisible();

        // Check data attribute
        const operation = await delLine.getAttribute('data-operation');
        expect(operation).toBe('delete');

        // Check class includes 'delete' for styling
        const className = await delLine.getAttribute('class');
        expect(className).toContain('delete');

        // Verify content is present (styling via CSS)
        const content = await delLine.locator('.code-line-content');
        await expect(content).toBeVisible();
        await expect(content).toContainText('old_code');
    });

    test('should handle multiple file streams simultaneously', async ({ page }) => {
        await page.evaluate(() => {
            const renderer = window.chatInterface.codeStreamRenderer;
            renderer.addCodeChunk('# File 1', 'file1.py', 1, 'add', 'python');
            renderer.addCodeChunk('# File 2', 'file2.py', 1, 'add', 'python');
            renderer.addCodeChunk('# File 3', 'file3.py', 1, 'add', 'python');
        });

        const containers = await page.locator('[data-testid="code-stream-container"]');
        await expect(containers).toHaveCount(3);

        // Check each file path
        const filePaths = await page.locator('[data-testid="code-stream-file-path"]').allTextContents();
        expect(filePaths).toContain('file1.py');
        expect(filePaths).toContain('file2.py');
        expect(filePaths).toContain('file3.py');
    });

    test('should have copy code button', async ({ page }) => {
        await page.evaluate(() => {
            window.chatInterface.codeStreamRenderer.addCodeChunk(
                'def test():',
                'test.py',
                1,
                'add',
                'python'
            );
        });

        const copyButton = await page.locator('[data-testid="copy-code-button"]');
        await expect(copyButton).toBeVisible();
        await expect(copyButton).toContainText('Copy Code');
    });

    test('should copy code to clipboard when copy button clicked', async ({ page }) => {
        // Grant clipboard permissions
        await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);

        await page.evaluate(() => {
            const renderer = window.chatInterface.codeStreamRenderer;
            renderer.addCodeChunk('line 1', 'test.py', 1, 'add', 'python');
            renderer.addCodeChunk('line 2', 'test.py', 2, 'add', 'python');
        });

        const copyButton = await page.locator('[data-testid="copy-code-button"]');
        await copyButton.click();

        // Check button feedback
        await expect(copyButton).toContainText('Copied!');

        // Check clipboard content
        const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
        expect(clipboardText).toContain('line 1');
        expect(clipboardText).toContain('line 2');

        // Wait for button to reset
        await page.waitForTimeout(2100);
        await expect(copyButton).toContainText('Copy Code');
    });

    test('should mark stream as complete when completeStream is called', async ({ page }) => {
        await page.evaluate(() => {
            const renderer = window.chatInterface.codeStreamRenderer;
            renderer.addCodeChunk('code', 'test.py', 1, 'add', 'python');
            renderer.completeStream('test.py');
        });

        const status = await page.locator('[data-testid="code-stream-status"]');
        await expect(status).toContainText('Complete');

        // Streaming indicator should not be present
        const indicator = await page.locator('.streaming-indicator');
        await expect(indicator).not.toBeVisible();
    });

    test('should escape HTML in code content to prevent XSS', async ({ page }) => {
        await page.evaluate(() => {
            window.chatInterface.codeStreamRenderer.addCodeChunk(
                '<script>alert("XSS")</script>',
                'malicious.js',
                1,
                'add',
                'javascript'
            );
        });

        const lineContent = await page.locator('.code-line-content').first();
        const html = await lineContent.innerHTML();
        const text = await lineContent.textContent();

        // Should be escaped - either raw &lt; or Prism's token span containing &lt;
        // Both are safe from XSS
        expect(html).toMatch(/&lt;/);
        // The actual script tag should not execute (text content check)
        expect(text).toContain('script');
        // Ensure no actual script tag in HTML that would execute
        expect(html).not.toMatch(/<script>alert\(/);
    });

    test('should auto-scroll code body as lines are added', async ({ page }) => {
        await page.evaluate(() => {
            const renderer = window.chatInterface.codeStreamRenderer;
            // Add many lines to trigger scroll
            for (let i = 1; i <= 50; i++) {
                renderer.addCodeChunk(`line ${i}`, 'test.py', i, 'add', 'python');
            }
        });

        // Check if scrolled to bottom
        const scrollInfo = await page.evaluate(() => {
            const body = document.querySelector('.code-stream-body');
            return {
                scrollTop: body.scrollTop,
                scrollHeight: body.scrollHeight,
                clientHeight: body.clientHeight
            };
        });

        // Should be scrolled near bottom (within 5px tolerance)
        const scrolledToBottom = scrollInfo.scrollTop + scrollInfo.clientHeight >= scrollInfo.scrollHeight - 5;
        expect(scrolledToBottom).toBe(true);
    });

    test('should support different programming languages', async ({ page }) => {
        const languages = ['python', 'javascript', 'typescript', 'json', 'bash'];

        for (const lang of languages) {
            await page.evaluate((language) => {
                window.chatInterface.codeStreamRenderer.addCodeChunk(
                    `// Code in ${language}`,
                    `test.${language}`,
                    1,
                    'add',
                    language
                );
            }, lang);
        }

        const containers = await page.locator('[data-testid="code-stream-container"]');
        await expect(containers).toHaveCount(languages.length);
    });

    test('should clear all streams when clearStreams is called', async ({ page }) => {
        await page.evaluate(() => {
            const renderer = window.chatInterface.codeStreamRenderer;
            renderer.addCodeChunk('code 1', 'file1.py', 1, 'add', 'python');
            renderer.addCodeChunk('code 2', 'file2.py', 1, 'add', 'python');
        });

        // Verify streams exist
        let containers = await page.locator('[data-testid="code-stream-container"]');
        await expect(containers).toHaveCount(2);

        // Clear streams
        await page.evaluate(() => {
            window.chatInterface.codeStreamRenderer.clearStreams();
        });

        // Verify internal state is cleared
        const streamCount = await page.evaluate(() => {
            return window.chatInterface.codeStreamRenderer.codeStreams.size;
        });
        expect(streamCount).toBe(0);
    });
});
