/**
 * Playwright Tests for Code Block Rendering with Syntax Highlighting - AI-134
 * REQ-CHAT-003: Code blocks in AI messages must render with syntax highlighting,
 * copy-to-clipboard button, file path annotation, and diff view support.
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8420';

/**
 * Helper: navigate to the dashboard and wait for chat interface to be ready.
 */
async function loadDashboard(page) {
    // Server serves dashboard at root path (not /dashboard.html)
    await page.goto(`${BASE_URL}/`);
    await page.waitForFunction(() => window.chatInterface !== undefined, { timeout: 10000 });
}

/**
 * Helper: inject a raw AI message with the given text directly into the chat interface.
 * This bypasses the simulated AI response and injects any content we want.
 */
async function injectAiMessage(page, text) {
    await page.evaluate((msgText) => {
        window.chatInterface.addMessage(msgText, 'ai', 'claude', 'claude-opus-4');
    }, text);
    // Give highlight.js time to run
    await page.waitForTimeout(300);
}

// -----------------------------------------------------------------------
// Test Suite
// -----------------------------------------------------------------------

test.describe('AI-134: Code Block Rendering with Syntax Highlighting', () => {

    test('renders code block wrapper for python code block', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "Here is some code:\n```python\nprint('hello')\n```");
        const wrapper = page.locator('[data-testid="code-block-wrapper"]').first();
        await expect(wrapper).toBeVisible();
    });

    test('renders language badge in code block header', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```python\nprint('hello')\n```");
        const badge = page.locator('[data-testid="code-language-badge"]').first();
        await expect(badge).toBeVisible();
        await expect(badge).toContainText('python');
    });

    test('renders copy button in code block header', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```javascript\nconsole.log('hi');\n```");
        const copyBtn = page.locator('[data-testid="copy-code-btn"]').first();
        await expect(copyBtn).toBeVisible();
        await expect(copyBtn).toHaveText('Copy');
    });

    test('copy button has correct CSS class', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```bash\necho hello\n```");
        const copyBtn = page.locator('.copy-code-btn').first();
        await expect(copyBtn).toBeVisible();
        await expect(copyBtn).toHaveClass(/copy-code-btn/);
    });

    test('renders file path annotation when filepath comment is present', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```python\n# filepath: src/main.py\nprint('hello')\n```");
        const filePath = page.locator('[data-testid="code-file-path"]').first();
        await expect(filePath).toBeVisible();
        await expect(filePath).toContainText('src/main.py');
    });

    test('renders file path annotation with // filepath: syntax', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```javascript\n// filepath: app/index.js\nconsole.log('hi');\n```");
        const filePath = page.locator('[data-testid="code-file-path"]').first();
        await expect(filePath).toBeVisible();
        await expect(filePath).toContainText('app/index.js');
    });

    test('renders diff block with green additions and red deletions', async ({ page }) => {
        await loadDashboard(page);
        const diffCode = "```diff\n-old line\n+new line\n unchanged\n```";
        await injectAiMessage(page, diffCode);

        // Check diff-addition (green) line
        const addition = page.locator('.diff-addition').first();
        await expect(addition).toBeVisible();
        await expect(addition).toContainText('+new line');

        // Check diff-deletion (red) line
        const deletion = page.locator('.diff-deletion').first();
        await expect(deletion).toBeVisible();
        await expect(deletion).toContainText('-old line');
    });

    test('diff additions have green color styling', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```diff\n+added line\n-removed line\n```");

        const addition = page.locator('.diff-addition').first();
        await expect(addition).toBeVisible();
        // Verify the color style is applied (green = #4caf50)
        const color = await addition.evaluate(el => getComputedStyle(el).color);
        // Should be a green-ish color (rgb values for #4caf50 are 76, 175, 80)
        expect(color).toMatch(/rgb\(76,\s*175,\s*80\)/);
    });

    test('diff deletions have red color styling', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```diff\n+added line\n-removed line\n```");

        const deletion = page.locator('.diff-deletion').first();
        await expect(deletion).toBeVisible();
        // Verify the color style is applied (red = #f44336, rgb 244, 67, 54)
        const color = await deletion.evaluate(el => getComputedStyle(el).color);
        expect(color).toMatch(/rgb\(244,\s*67,\s*54\)/);
    });

    test('renders javascript code block with correct language badge', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```javascript\nconst x = 42;\nconsole.log(x);\n```");
        const badge = page.locator('[data-testid="code-language-badge"]').first();
        await expect(badge).toContainText('javascript');
        const wrapper = page.locator('[data-testid="code-block-wrapper"]').first();
        await expect(wrapper).toHaveAttribute('data-language', 'javascript');
    });

    test('renders bash code block with correct language badge', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```bash\necho 'hello world'\nls -la\n```");
        const badge = page.locator('[data-testid="code-language-badge"]').first();
        await expect(badge).toContainText('bash');
    });

    test('renders json code block with correct language badge', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, '```json\n{"key": "value", "num": 42}\n```');
        const badge = page.locator('[data-testid="code-language-badge"]').first();
        await expect(badge).toContainText('json');
    });

    test('renders html code block with correct language badge', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, '```html\n<div class="container">Hello</div>\n```');
        const badge = page.locator('[data-testid="code-language-badge"]').first();
        await expect(badge).toContainText('html');
    });

    test('renders css code block with correct language badge', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, '```css\n.container { color: red; }\n```');
        const badge = page.locator('[data-testid="code-language-badge"]').first();
        await expect(badge).toContainText('css');
    });

    test('renders multiple code blocks in a single message', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page,
            "First block:\n```python\nprint('hello')\n```\nSecond block:\n```javascript\nconsole.log('world');\n```"
        );
        const wrappers = page.locator('[data-testid="code-block-wrapper"]');
        await expect(wrappers).toHaveCount(2);
    });

    test('code block content is accessible by id for clipboard copy', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, "```python\nprint('clipboard test')\n```");
        // The code element should have an id attribute set
        const codeEl = page.locator('[data-testid="code-block-content"]').first();
        await expect(codeEl).toBeVisible();
        const codeId = await codeEl.getAttribute('id');
        expect(codeId).toBeTruthy();
        expect(codeId).toMatch(/^code-block-/);
    });

    test('non-code text in AI message renders as plain text (not a code block)', async ({ page }) => {
        await loadDashboard(page);
        await injectAiMessage(page, 'This is just a plain text response with no code.');
        // No code block wrappers should be present for this message
        const wrappers = page.locator('[data-testid="code-block-wrapper"]');
        await expect(wrappers).toHaveCount(0);
    });

});
