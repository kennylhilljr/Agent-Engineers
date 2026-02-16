/**
 * AI-72: Model Selector per Provider - Browser Integration Tests
 *
 * Playwright tests to validate model selector functionality in real browser environment
 */

const { test, expect } = require('@playwright/test');
const path = require('path');

const TEST_FILE = path.join(__dirname, '../test_chat.html');
const TEST_URL = `file://${TEST_FILE}`;

test.describe('AI-72: Model Selector Browser Tests', () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to test page
        await page.goto(TEST_URL);
        // Wait for page to be ready
        await page.waitForLoadState('domcontentloaded');
        // Clear sessionStorage
        await page.evaluate(() => sessionStorage.clear());
        await page.reload();
    });

    // ==========================================
    // Test Group 1: Initial State
    // ==========================================

    test.describe('Initial State', () => {
        test('should display model selector with Claude models by default', async ({ page }) => {
            const modelSelector = await page.locator('#ai-model-selector');
            await expect(modelSelector).toBeVisible();

            const options = await modelSelector.locator('option').all();
            expect(options.length).toBe(3);

            const firstOption = await options[0].textContent();
            expect(firstOption).toBe('Haiku 4.5');
        });

        test('should display default model badge (Haiku 4.5)', async ({ page }) => {
            const modelBadge = await page.locator('#model-badge');
            await expect(modelBadge).toBeVisible();
            await expect(modelBadge).toHaveText('Haiku 4.5');
        });

        test('should have default model selected in dropdown', async ({ page }) => {
            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('haiku-4.5');
        });
    });

    // ==========================================
    // Test Group 2: Provider Change Updates Models
    // ==========================================

    test.describe('Provider Change Updates Models', () => {
        test('should show Claude models: Haiku 4.5, Sonnet 4.5, Opus 4.6', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'claude');

            const options = await page.locator('#ai-model-selector option').allTextContents();
            expect(options).toEqual(['Haiku 4.5', 'Sonnet 4.5', 'Opus 4.6']);
        });

        test('should show ChatGPT models: GPT-4o, o1, o3-mini, o4-mini', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'chatgpt');

            const options = await page.locator('#ai-model-selector option').allTextContents();
            expect(options).toEqual(['GPT-4o', 'o1', 'o3-mini', 'o4-mini']);
        });

        test('should show Gemini models: 2.5 Flash, 2.5 Pro, 2.0 Flash', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'gemini');

            const options = await page.locator('#ai-model-selector option').allTextContents();
            expect(options).toEqual(['2.5 Flash', '2.5 Pro', '2.0 Flash']);
        });

        test('should show Groq models: Llama 3.3 70B, Mixtral 8x7B', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'groq');

            const options = await page.locator('#ai-model-selector option').allTextContents();
            expect(options).toEqual(['Llama 3.3 70B', 'Mixtral 8x7B']);
        });

        test('should show KIMI model: Moonshot', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'kimi');

            const options = await page.locator('#ai-model-selector option').allTextContents();
            expect(options).toEqual(['Moonshot']);
        });

        test('should show Windsurf model: Cascade', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'windsurf');

            const options = await page.locator('#ai-model-selector option').allTextContents();
            expect(options).toEqual(['Cascade']);
        });
    });

    // ==========================================
    // Test Group 3: Default Model Highlighting
    // ==========================================

    test.describe('Default Model Highlighting', () => {
        test('should highlight Haiku 4.5 as default for Claude', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'claude');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('haiku-4.5');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Haiku 4.5');
        });

        test('should highlight GPT-4o as default for ChatGPT', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'chatgpt');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('gpt-4o');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('GPT-4o');
        });

        test('should highlight 2.5 Flash as default for Gemini', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'gemini');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('2.5-flash');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('2.5 Flash');
        });

        test('should highlight Llama 3.3 70B as default for Groq', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'groq');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('llama-3.3-70b');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Llama 3.3 70B');
        });

        test('should highlight Moonshot as default for KIMI', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'kimi');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('moonshot');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Moonshot');
        });

        test('should highlight Cascade as default for Windsurf', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'windsurf');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('cascade');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Cascade');
        });
    });

    // ==========================================
    // Test Group 4: Model Selection
    // ==========================================

    test.describe('Model Selection', () => {
        test('should allow selecting Sonnet 4.5 for Claude', async ({ page }) => {
            await page.selectOption('#ai-model-selector', 'sonnet-4.5');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('sonnet-4.5');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Sonnet 4.5');
        });

        test('should allow selecting Opus 4.6 for Claude', async ({ page }) => {
            await page.selectOption('#ai-model-selector', 'opus-4.6');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('opus-4.6');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Opus 4.6');
        });

        test('should allow selecting o1 for ChatGPT', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'chatgpt');
            await page.selectOption('#ai-model-selector', 'o1');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('o1');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('o1');
        });

        test('should allow selecting 2.5 Pro for Gemini', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'gemini');
            await page.selectOption('#ai-model-selector', '2.5-pro');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('2.5-pro');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('2.5 Pro');
        });

        test('should allow selecting Mixtral 8x7B for Groq', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'groq');
            await page.selectOption('#ai-model-selector', 'mixtral-8x7b');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('mixtral-8x7b');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Mixtral 8x7B');
        });
    });

    // ==========================================
    // Test Group 5: Message Persistence
    // ==========================================

    test.describe('Model Selection Persists After Sending Message', () => {
        test('should maintain model selection after sending message', async ({ page }) => {
            // Select Sonnet 4.5
            await page.selectOption('#ai-model-selector', 'sonnet-4.5');

            // Send a message
            await page.fill('#chat-input', 'Test message');
            await page.click('#chat-send-btn');

            // Wait for message to appear
            await page.waitForSelector('[data-testid="chat-message-user"]');

            // Verify model selection persists
            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('sonnet-4.5');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Sonnet 4.5');
        });

        test('should include model in AI response after sending message', async ({ page }) => {
            // Select Opus 4.6
            await page.selectOption('#ai-model-selector', 'opus-4.6');

            // Send a message
            await page.fill('#chat-input', 'Hello');
            await page.click('#chat-send-btn');

            // Wait for AI response
            await page.waitForSelector('[data-testid="chat-message-ai"]', { timeout: 2000 });

            // Check if AI response includes model name
            const aiMessage = await page.locator('[data-testid="chat-message-ai"]').last().textContent();
            expect(aiMessage).toContain('Claude');
            expect(aiMessage).toContain('Opus 4.6');
        });

        test('should send multiple messages with different models', async ({ page }) => {
            // Send with Haiku
            await page.selectOption('#ai-model-selector', 'haiku-4.5');
            await page.fill('#chat-input', 'Message 1');
            await page.click('#chat-send-btn');
            await page.waitForSelector('[data-testid="chat-message-ai"]', { timeout: 2000 });

            // Change to Sonnet and send
            await page.selectOption('#ai-model-selector', 'sonnet-4.5');
            await page.fill('#chat-input', 'Message 2');
            await page.click('#chat-send-btn');
            await page.waitForSelector('[data-testid="chat-message-user"]', { count: 2 });

            // Verify model still selected
            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('sonnet-4.5');
        });
    });

    // ==========================================
    // Test Group 6: Session Persistence
    // ==========================================

    test.describe('Session Persistence After Refresh', () => {
        test('should persist model selection after page refresh', async ({ page }) => {
            // Select Opus 4.6
            await page.selectOption('#ai-model-selector', 'opus-4.6');

            // Refresh page
            await page.reload();
            await page.waitForLoadState('domcontentloaded');

            // Verify model selection persisted
            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('opus-4.6');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Opus 4.6');
        });

        test('should persist both provider and model after refresh', async ({ page }) => {
            // Select ChatGPT and o1
            await page.selectOption('#ai-provider-selector', 'chatgpt');
            await page.selectOption('#ai-model-selector', 'o1');

            // Refresh page
            await page.reload();
            await page.waitForLoadState('domcontentloaded');

            // Verify both persisted
            const providerValue = await page.locator('#ai-provider-selector').inputValue();
            expect(providerValue).toBe('chatgpt');

            const modelValue = await page.locator('#ai-model-selector').inputValue();
            expect(modelValue).toBe('o1');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('o1');
        });

        test('should use default model if no saved selection', async ({ page }) => {
            // Clear storage
            await page.evaluate(() => sessionStorage.clear());
            await page.reload();
            await page.waitForLoadState('domcontentloaded');

            // Should use Claude Haiku 4.5 as default
            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('haiku-4.5');
        });
    });

    // ==========================================
    // Test Group 7: UI Interaction
    // ==========================================

    test.describe('UI Interaction', () => {
        test('should update model dropdown immediately when provider changes', async ({ page }) => {
            const initialOptions = await page.locator('#ai-model-selector option').count();
            expect(initialOptions).toBe(3); // Claude has 3 models

            await page.selectOption('#ai-provider-selector', 'chatgpt');

            const newOptions = await page.locator('#ai-model-selector option').count();
            expect(newOptions).toBe(4); // ChatGPT has 4 models
        });

        test('should have functional model selector dropdown', async ({ page }) => {
            const modelSelector = await page.locator('#ai-model-selector');

            // Should be enabled and visible
            await expect(modelSelector).toBeEnabled();
            await expect(modelSelector).toBeVisible();

            // Should allow interaction
            await modelSelector.click();
            await page.keyboard.press('ArrowDown');
            await page.keyboard.press('Enter');

            // Model should have changed
            const selectedValue = await modelSelector.inputValue();
            expect(selectedValue).toBe('sonnet-4.5');
        });

        test('should display model badge with correct styling', async ({ page }) => {
            const modelBadge = await page.locator('#model-badge');

            await expect(modelBadge).toBeVisible();
            await expect(modelBadge).toHaveCSS('display', /flex/);
        });
    });

    // ==========================================
    // Test Group 8: Accessibility
    // ==========================================

    test.describe('Accessibility', () => {
        test('should have aria-label on model selector', async ({ page }) => {
            const ariaLabel = await page.locator('#ai-model-selector').getAttribute('aria-label');
            expect(ariaLabel).toBe('Select AI Model');
        });

        test('should have label for model selector', async ({ page }) => {
            const label = await page.locator('label[for="ai-model-selector"]');
            await expect(label).toBeVisible();
            await expect(label).toHaveText('Model:');
        });

        test('should have data-testid attributes for testing', async ({ page }) => {
            const modelSelector = await page.locator('[data-testid="ai-model-selector"]');
            await expect(modelSelector).toBeVisible();

            const modelBadge = await page.locator('[data-testid="model-badge"]');
            await expect(modelBadge).toBeVisible();
        });
    });

    // ==========================================
    // Test Group 9: Integration with Provider
    // ==========================================

    test.describe('Integration with Provider Selector', () => {
        test('should work alongside provider selector without conflicts', async ({ page }) => {
            // Change provider
            await page.selectOption('#ai-provider-selector', 'gemini');

            // Both badges should update
            const providerBadge = await page.locator('#provider-badge').textContent();
            expect(providerBadge).toBe('Gemini');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('2.5 Flash');
        });

        test('should maintain independent state for provider and model', async ({ page }) => {
            // Select provider
            await page.selectOption('#ai-provider-selector', 'chatgpt');
            const provider = await page.locator('#ai-provider-selector').inputValue();

            // Select model
            await page.selectOption('#ai-model-selector', 'o3-mini');
            const model = await page.locator('#ai-model-selector').inputValue();

            // Both should be independently set
            expect(provider).toBe('chatgpt');
            expect(model).toBe('o3-mini');
        });
    });

    // ==========================================
    // Test Group 10: Edge Cases
    // ==========================================

    test.describe('Edge Cases', () => {
        test('should handle rapid provider switching', async ({ page }) => {
            await page.selectOption('#ai-provider-selector', 'chatgpt');
            await page.selectOption('#ai-provider-selector', 'gemini');
            await page.selectOption('#ai-provider-selector', 'groq');
            await page.selectOption('#ai-provider-selector', 'claude');

            // Should end up with Claude models
            const options = await page.locator('#ai-model-selector option').count();
            expect(options).toBe(3);

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('haiku-4.5');
        });

        test('should handle rapid model switching', async ({ page }) => {
            await page.selectOption('#ai-model-selector', 'sonnet-4.5');
            await page.selectOption('#ai-model-selector', 'opus-4.6');
            await page.selectOption('#ai-model-selector', 'haiku-4.5');

            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('haiku-4.5');

            const modelBadge = await page.locator('#model-badge').textContent();
            expect(modelBadge).toBe('Haiku 4.5');
        });

        test('should reset to default when switching to provider with single model', async ({ page }) => {
            // Select custom model for Claude
            await page.selectOption('#ai-model-selector', 'opus-4.6');

            // Switch to KIMI (single model)
            await page.selectOption('#ai-provider-selector', 'kimi');

            // Should auto-select the only available model
            const selectedValue = await page.locator('#ai-model-selector').inputValue();
            expect(selectedValue).toBe('moonshot');
        });
    });
});

console.log('AI-72 Model Selector Browser Tests Loaded');
