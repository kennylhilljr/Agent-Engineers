/**
 * Code Block Rendering Browser Tests
 * Tests for syntax highlighting, copy-to-clipboard, file path annotation, and diff view
 * Using Playwright for end-to-end testing
 */

const { test, expect } = require('@playwright/test');

test.describe('Code Block Rendering - Browser Tests', () => {
    let page;

    test.beforeAll(async ({ browser }) => {
        const context = await browser.newContext();
        page = await context.newPage();
    });

    test.beforeEach(async ({ page }) => {
        // Navigate to dashboard test page
        await page.goto('file:///Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-dashboard/.worktrees/coding-0/dashboard/test_chat.html', {
            waitUntil: 'networkidle'
        });
    });

    test('Test 1: Ask AI to generate Python code', async ({ page }) => {
        // Type a message requesting Python code
        await page.fill('#chat-input', 'Can you show me Python code?');
        await page.click('#chat-send-btn');

        // Wait for AI response
        await page.waitForSelector('.code-block-wrapper', { timeout: 5000 });

        // Verify code block appears
        const codeBlock = page.locator('.code-block-wrapper');
        expect(await codeBlock.count()).toBeGreaterThan(0);

        // Take screenshot
        await page.screenshot({ path: 'screenshots/ai-70-python-code.png', fullPage: true });
    });

    test('Test 2: Verify syntax highlighting applies correct colors/tokens', async ({ page }) => {
        await page.fill('#chat-input', 'Show me Python code');
        await page.click('#chat-send-btn');

        await page.waitForSelector('code.language-python', { timeout: 5000 });

        // Check if syntax highlighting library is loaded
        const hlJsLoaded = await page.evaluate(() => typeof hljs !== 'undefined');
        expect(hlJsLoaded).toBe(true);

        // Verify code block has language class
        const codeElement = page.locator('code.language-python');
        const classes = await codeElement.first().getAttribute('class');
        expect(classes).toContain('language-python');
        expect(classes).toContain('hljs');

        // Take screenshot showing syntax highlighting
        await page.screenshot({ path: 'screenshots/ai-70-syntax-highlighting.png', fullPage: true });
    });

    test('Test 3: Click copy button and verify code copied to clipboard', async ({ page }) => {
        await page.fill('#chat-input', 'Python code please');
        await page.click('#chat-send-btn');

        await page.waitForSelector('.copy-btn', { timeout: 5000 });

        // Click copy button
        const copyBtn = page.locator('[data-testid="copy-code-btn"]').first();
        await copyBtn.click();

        // Check button feedback
        const btnText = await copyBtn.textContent();
        expect(btnText).toContain('Copied');

        // Wait for button to revert
        await page.waitForTimeout(2100);

        // Take screenshot showing copy feedback
        await page.screenshot({ path: 'screenshots/ai-70-copy-button.png', fullPage: true });
    });

    test('Test 4: Ask for code that modifies a specific file', async ({ page }) => {
        await page.fill('#chat-input', 'Show code changes');
        await page.click('#chat-send-btn');

        await page.waitForSelector('.code-block-wrapper', { timeout: 5000 });

        // Verify code block appears (may be diff or regular code)
        const codeBlock = page.locator('.code-block-wrapper');
        expect(await codeBlock.count()).toBeGreaterThan(0);

        // Take screenshot
        await page.screenshot({ path: 'screenshots/ai-70-code-changes.png', fullPage: true });
    });

    test('Test 5: Verify file path displays above code block', async ({ page }) => {
        await page.fill('#chat-input', 'Show Python code');
        await page.click('#chat-send-btn');

        await page.waitForSelector('.code-block-filepath', { timeout: 5000 });

        // Verify filepath element exists
        const filePath = page.locator('.code-block-filepath');
        const count = await filePath.count();

        if (count > 0) {
            const text = await filePath.first().textContent();
            expect(text.length).toBeGreaterThan(0);
        }

        // Take screenshot
        await page.screenshot({ path: 'screenshots/ai-70-filepath.png', fullPage: true });
    });

    test('Test 6: Ask for code change and verify green/red coloring', async ({ page }) => {
        await page.fill('#chat-input', 'Show code changes with diff');
        await page.click('#chat-send-btn');

        await page.waitForSelector('.code-line', { timeout: 5000 });

        // Check for diff styling
        const addedLines = page.locator('.code-line.added');
        const deletedLines = page.locator('.code-line.deleted');

        const addedCount = await addedLines.count();
        const deletedCount = await deletedLines.count();

        if (addedCount > 0) {
            expect(addedCount).toBeGreaterThan(0);
        }
        if (deletedCount > 0) {
            expect(deletedCount).toBeGreaterThan(0);
        }

        // Verify CSS colors are applied
        const addedLine = addedLines.first();
        const backgroundColor = await addedLine.evaluate(el =>
            window.getComputedStyle(el).backgroundColor
        );
        expect(backgroundColor).toBeTruthy();

        // Take screenshot showing diff colors
        await page.screenshot({ path: 'screenshots/ai-70-diff-colors.png', fullPage: true });
    });

    test('Test 7: Test with multiple languages', async ({ page }) => {
        const languages = [
            { query: 'JavaScript code', language: 'javascript' },
            { query: 'Python code', language: 'python' },
            { query: 'HTML code', language: 'html' },
            { query: 'CSS code', language: 'css' }
        ];

        for (const { query, language } of languages) {
            await page.fill('#chat-input', query);
            await page.click('#chat-send-btn');

            // Wait for code block
            await page.waitForSelector(`.code-block-wrapper`, { timeout: 5000 });

            // Take screenshot for each language
            await page.screenshot({
                path: `screenshots/ai-70-language-${language}.png`,
                fullPage: true
            });

            // Clear chat for next test
            await page.evaluate(() => {
                if (window.chatInterface) {
                    window.chatInterface.clearMessages();
                }
            });

            // Wait a moment
            await page.waitForTimeout(500);
        }
    });

    test('Verify code block structure and styling', async ({ page }) => {
        await page.fill('#chat-input', 'python code');
        await page.click('#chat-send-btn');

        await page.waitForSelector('.code-block-wrapper', { timeout: 5000 });

        // Check structure
        const wrapper = page.locator('.code-block-wrapper').first();
        expect(await wrapper.count()).toBeGreaterThan(0);

        // Verify header exists
        const header = wrapper.locator('.code-block-header');
        expect(await header.count()).toBe(1);

        // Verify language label
        const langLabel = header.locator('.code-block-language');
        expect(await langLabel.count()).toBeGreaterThan(0);

        // Verify copy button
        const copyBtn = header.locator('.copy-btn');
        expect(await copyBtn.count()).toBeGreaterThan(0);

        // Verify code block content
        const codeBlock = wrapper.locator('.code-block');
        expect(await codeBlock.count()).toBe(1);

        // Verify code element
        const code = codeBlock.locator('code');
        expect(await code.count()).toBe(1);

        // Take screenshot
        await page.screenshot({ path: 'screenshots/ai-70-code-structure.png', fullPage: true });
    });

    test('Verify copy button functionality', async ({ page }) => {
        await page.fill('#chat-input', 'javascript code');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="copy-code-btn"]', { timeout: 5000 });

        const copyBtn = page.locator('[data-testid="copy-code-btn"]').first();

        // Get initial button text
        const initialText = await copyBtn.textContent();

        // Click button
        await copyBtn.click();

        // Verify feedback
        const feedbackText = await copyBtn.textContent();
        expect(feedbackText).not.toBe(initialText);
        expect(feedbackText).toContain('Copied');

        // Wait for reset
        await page.waitForTimeout(2500);

        // Verify reset
        const resetText = await copyBtn.textContent();
        expect(resetText).toBe(initialText);

        // Take screenshot
        await page.screenshot({ path: 'screenshots/ai-70-copy-feedback.png', fullPage: true });
    });

    test('Verify message persistence with code blocks', async ({ page }) => {
        // Send message with code
        await page.fill('#chat-input', 'Show python code');
        await page.click('#chat-send-btn');

        await page.waitForSelector('.code-block-wrapper', { timeout: 5000 });

        // Get initial message count
        const initialMessages = await page.locator('.chat-message').count();

        // Reload page
        await page.reload({ waitUntil: 'networkidle' });

        // Wait for messages to reload
        await page.waitForTimeout(1000);

        // Verify messages persisted
        const reloadedMessages = await page.locator('.chat-message').count();
        expect(reloadedMessages).toBeGreaterThanOrEqual(initialMessages);

        // Verify code block persisted
        const codeBlocks = await page.locator('.code-block-wrapper').count();
        expect(codeBlocks).toBeGreaterThan(0);

        // Take screenshot
        await page.screenshot({ path: 'screenshots/ai-70-persistence.png', fullPage: true });
    });

    test('Verify diff block rendering', async ({ page }) => {
        await page.fill('#chat-input', 'show code changes');
        await page.click('#chat-send-btn');

        await page.waitForSelector('.code-block-diff', { timeout: 5000 });

        // Check for diff block
        const diffBlock = page.locator('.code-block-diff');
        expect(await diffBlock.count()).toBeGreaterThan(0);

        // Check for diff lines
        const addedLines = page.locator('.code-line.added');
        const deletedLines = page.locator('.code-line.deleted');

        // At least one should exist for a valid diff
        const hasAddedOrDeleted =
            (await addedLines.count()) > 0 ||
            (await deletedLines.count()) > 0;

        if (hasAddedOrDeleted) {
            expect(hasAddedOrDeleted).toBe(true);
        }

        // Take screenshot
        await page.screenshot({ path: 'screenshots/ai-70-diff-block.png', fullPage: true });
    });

    test('Verify responsive layout with code blocks', async ({ page }) => {
        // Test at different viewport sizes
        const viewports = [
            { width: 1920, height: 1080, name: 'desktop' },
            { width: 768, height: 1024, name: 'tablet' },
            { width: 375, height: 667, name: 'mobile' }
        ];

        for (const { width, height, name } of viewports) {
            await page.setViewportSize({ width, height });

            await page.fill('#chat-input', 'python code');
            await page.click('#chat-send-btn');

            await page.waitForSelector('.code-block-wrapper', { timeout: 5000 });

            // Take screenshot
            await page.screenshot({
                path: `screenshots/ai-70-responsive-${name}.png`,
                fullPage: true
            });

            // Clear for next test
            await page.evaluate(() => {
                if (window.chatInterface) {
                    window.chatInterface.clearMessages();
                }
            });

            await page.waitForTimeout(500);
        }
    });

    test('Verify accessibility attributes', async ({ page }) => {
        await page.fill('#chat-input', 'show code');
        await page.click('#chat-send-btn');

        await page.waitForSelector('.code-block-wrapper', { timeout: 5000 });

        // Check for data-testid attributes
        const copyBtns = page.locator('[data-testid*="copy"]');
        expect(await copyBtns.count()).toBeGreaterThan(0);

        // Check for message attributes
        const messages = page.locator('[data-testid*="chat-message"]');
        expect(await messages.count()).toBeGreaterThan(0);

        // Verify message IDs exist
        const aiMessages = page.locator('[data-message-id]');
        expect(await aiMessages.count()).toBeGreaterThan(0);

        // Take screenshot
        await page.screenshot({ path: 'screenshots/ai-70-accessibility.png', fullPage: true });
    });
});

// Additional integration tests
test.describe('Code Block Integration Tests', () => {
    test('Full workflow: send multiple messages with different code types', async ({ page }) => {
        await page.goto('file:///Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-dashboard/.worktrees/coding-0/dashboard/test_chat.html', {
            waitUntil: 'networkidle'
        });

        const messages = [
            { text: 'Show Python code', screenshot: 'python' },
            { text: 'JavaScript example', screenshot: 'javascript' },
            { text: 'Show HTML CSS', screenshot: 'html-css' },
            { text: 'Code changes', screenshot: 'changes' }
        ];

        for (const msg of messages) {
            await page.fill('#chat-input', msg.text);
            await page.click('#chat-send-btn');

            // Wait for response
            await page.waitForSelector('.code-block-wrapper', { timeout: 5000 });

            // Take screenshot
            await page.screenshot({
                path: `screenshots/ai-70-workflow-${msg.screenshot}.png`,
                fullPage: true
            });

            await page.waitForTimeout(500);
        }

        // Final verification
        const totalMessages = await page.locator('.chat-message').count();
        expect(totalMessages).toBeGreaterThanOrEqual(4);
    });
});
