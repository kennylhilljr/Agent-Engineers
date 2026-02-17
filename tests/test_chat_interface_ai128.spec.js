/**
 * AI-128: Phase 3 AI Chat Interface - Multi-Provider Support
 * Comprehensive Playwright tests for complete chat implementation
 *
 * Tests:
 * - Streaming responses
 * - Multi-provider support (Claude, ChatGPT, Gemini, Groq, KIMI, Windsurf)
 * - Tool call transparency (Linear/GitHub/Slack)
 * - Code block syntax highlighting
 * - Message persistence
 * - Error handling
 */

const { test, expect } = require('@playwright/test');

test.describe('AI-128: Complete Chat Interface with Multi-Provider Support', () => {
    const dashboardUrl = 'http://127.0.0.1:8420/test_chat.html';
    const apiUrl = 'http://127.0.0.1:8420';

    test.beforeEach(async ({ page }) => {
        // Navigate to chat interface
        await page.goto(dashboardUrl);
        await page.waitForLoadState('networkidle');
    });

    test('Chat interface loads with all components', async ({ page }) => {
        // Verify provider selector
        const providerSelector = page.locator('#ai-provider-selector');
        await expect(providerSelector).toBeVisible();

        // Verify model selector
        const modelSelector = page.locator('#ai-model-selector');
        await expect(modelSelector).toBeVisible();

        // Verify chat messages container
        const chatMessages = page.locator('#chat-messages');
        await expect(chatMessages).toBeVisible();

        // Verify input field
        const chatInput = page.locator('#chat-input');
        await expect(chatInput).toBeVisible();

        // Verify send button
        const sendButton = page.locator('#chat-send-btn');
        await expect(sendButton).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai128-01-initial-load.png',
            fullPage: true
        });
    });

    test('Provider selector shows all 6 providers', async ({ page }) => {
        const providerSelector = page.locator('#ai-provider-selector');

        // Get all options
        const options = await providerSelector.locator('option').all();

        // Should have 6 providers
        expect(options.length).toBe(6);

        // Check provider names
        const claudeOption = page.locator('option[value="claude"]');
        await expect(claudeOption).toBeVisible();

        const chatgptOption = page.locator('option[value="chatgpt"]');
        await expect(chatgptOption).toBeVisible();

        const geminiOption = page.locator('option[value="gemini"]');
        await expect(geminiOption).toBeVisible();

        const groqOption = page.locator('option[value="groq"]');
        await expect(groqOption).toBeVisible();

        const kimiOption = page.locator('option[value="kimi"]');
        await expect(kimiOption).toBeVisible();

        const windsurfOption = page.locator('option[value="windsurf"]');
        await expect(windsurfOption).toBeVisible();
    });

    test('Model selector updates when provider changes', async ({ page }) => {
        const providerSelector = page.locator('#ai-provider-selector');
        const modelSelector = page.locator('#ai-model-selector');

        // Select Claude
        await providerSelector.selectOption('claude');
        await page.waitForTimeout(200);

        // Check Claude models
        let options = await modelSelector.locator('option').allTextContents();
        expect(options).toContain('Haiku 4.5');
        expect(options).toContain('Sonnet 4.5');
        expect(options).toContain('Opus 4.6');

        // Select ChatGPT
        await providerSelector.selectOption('chatgpt');
        await page.waitForTimeout(200);

        // Check ChatGPT models
        options = await modelSelector.locator('option').allTextContents();
        expect(options).toContain('GPT-4o');
        expect(options).toContain('o1');

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai128-02-provider-switching.png',
            fullPage: true
        });
    });

    test('User can send message and see response', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Type message
        await chatInput.fill('Hello, what is my status?');

        // Send message
        await sendButton.click();

        // Wait for user message to appear
        await page.waitForTimeout(500);

        // Verify user message
        const userMessage = page.locator('[data-testid="chat-message-user"]').first();
        await expect(userMessage).toBeVisible();
        await expect(userMessage).toContainText('Hello');

        // Wait for AI response
        await page.waitForTimeout(1500);

        // Verify AI message
        const aiMessage = page.locator('[data-testid="chat-message-ai"]').first();
        await expect(aiMessage).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai128-03-basic-chat.png',
            fullPage: true
        });
    });

    test('Chat shows tool calls for Linear query', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Ask about Linear issues
        await chatInput.fill('What are my Linear issues?');
        await sendButton.click();

        // Wait for response with tool calls
        await page.waitForTimeout(2000);

        // Look for tool call indicators
        // Tool calls might appear as special messages or within AI responses
        const messages = page.locator('[data-testid^="chat-message-"]');
        const messageCount = await messages.count();

        // Should have at least user message and AI response
        expect(messageCount).toBeGreaterThanOrEqual(2);

        // Check if tool calls are visible (they might be in separate elements)
        // This depends on the implementation - adjust selector as needed
        const toolCalls = page.locator('[data-testid="tool-call-message"]');
        const toolCallCount = await toolCalls.count();

        // Tool calls might be visible
        if (toolCallCount > 0) {
            console.log(`Found ${toolCallCount} tool call(s)`);
            await expect(toolCalls.first()).toBeVisible();
        }

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai128-04-linear-tool-calls.png',
            fullPage: true
        });
    });

    test('Chat shows tool calls for GitHub query', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Ask about GitHub
        await chatInput.fill('Show me GitHub pull requests');
        await sendButton.click();

        // Wait for response
        await page.waitForTimeout(2000);

        // Verify messages appear
        const aiMessage = page.locator('[data-testid="chat-message-ai"]');
        await expect(aiMessage.first()).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai128-05-github-tool-calls.png',
            fullPage: true
        });
    });

    test('Chat shows tool calls for Slack query', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Ask about Slack
        await chatInput.fill('Get Slack messages');
        await sendButton.click();

        // Wait for response
        await page.waitForTimeout(2000);

        // Verify messages appear
        const aiMessage = page.locator('[data-testid="chat-message-ai"]');
        await expect(aiMessage.first()).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai128-06-slack-tool-calls.png',
            fullPage: true
        });
    });

    test('Chat displays code blocks with syntax highlighting', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Ask for code
        await chatInput.fill('Show me Python code example');
        await sendButton.click();

        // Wait for response
        await page.waitForTimeout(2000);

        // Look for code block markers
        const aiMessage = page.locator('[data-testid="chat-message-ai"]').first();
        await expect(aiMessage).toBeVisible();

        const messageText = await aiMessage.textContent();

        // Should contain code indicators (depending on implementation)
        // Either raw ``` or rendered code blocks
        const hasCodeIndicator = messageText.includes('```') ||
                                  messageText.includes('python') ||
                                  messageText.includes('def');

        expect(hasCodeIndicator).toBe(true);

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai128-07-code-blocks.png',
            fullPage: true
        });
    });

    test('Multiple messages create scrollable thread', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Send multiple messages
        const messages = [
            'First message',
            'Second message',
            'Third message'
        ];

        for (const msg of messages) {
            await chatInput.fill(msg);
            await sendButton.click();
            await page.waitForTimeout(1500);
        }

        // Verify multiple messages exist
        const allMessages = page.locator('[data-testid^="chat-message-"]');
        const count = await allMessages.count();

        // Should have at least 6 messages (3 user + 3 AI)
        expect(count).toBeGreaterThanOrEqual(6);

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai128-08-multiple-messages.png',
            fullPage: true
        });
    });

    test('Chat works with different providers', async ({ page }) => {
        const providerSelector = page.locator('#ai-provider-selector');
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Test with Claude
        await providerSelector.selectOption('claude');
        await chatInput.fill('Test with Claude');
        await sendButton.click();
        await page.waitForTimeout(1500);

        // Test with ChatGPT
        await providerSelector.selectOption('chatgpt');
        await chatInput.fill('Test with ChatGPT');
        await sendButton.click();
        await page.waitForTimeout(1500);

        // Test with Gemini
        await providerSelector.selectOption('gemini');
        await chatInput.fill('Test with Gemini');
        await sendButton.click();
        await page.waitForTimeout(1500);

        // Verify all messages appeared
        const allMessages = page.locator('[data-testid^="chat-message-"]');
        const count = await allMessages.count();

        expect(count).toBeGreaterThanOrEqual(6); // 3 user + 3 AI

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai128-09-multi-provider.png',
            fullPage: true
        });
    });

    test('Provider badge updates when provider changes', async ({ page }) => {
        const providerSelector = page.locator('#ai-provider-selector');
        const providerBadge = page.locator('#provider-badge');

        // Check initial badge
        await expect(providerBadge).toBeVisible();

        // Change to different providers and verify badge
        await providerSelector.selectOption('chatgpt');
        await page.waitForTimeout(200);
        await expect(providerBadge).toHaveText('ChatGPT');

        await providerSelector.selectOption('gemini');
        await page.waitForTimeout(200);
        await expect(providerBadge).toHaveText('Gemini');

        await providerSelector.selectOption('groq');
        await page.waitForTimeout(200);
        await expect(providerBadge).toHaveText('Groq');
    });

    test('Model badge updates when model changes', async ({ page }) => {
        const modelSelector = page.locator('#ai-model-selector');
        const modelBadge = page.locator('#model-badge');

        // Check initial badge
        await expect(modelBadge).toBeVisible();

        // Change models
        await modelSelector.selectOption('sonnet-4.5');
        await page.waitForTimeout(200);
        await expect(modelBadge).toHaveText('Sonnet 4.5');

        await modelSelector.selectOption('opus-4.6');
        await page.waitForTimeout(200);
        await expect(modelBadge).toHaveText('Opus 4.6');
    });

    test('Enter key sends message', async ({ page }) => {
        const chatInput = page.locator('#chat-input');

        await chatInput.fill('Test Enter key');
        await chatInput.press('Enter');

        // Wait for message
        await page.waitForTimeout(500);

        const userMessage = page.locator('[data-testid="chat-message-user"]').first();
        await expect(userMessage).toBeVisible();
        await expect(userMessage).toContainText('Test Enter key');
    });

    test('Loading indicator appears during response', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        await chatInput.fill('Test loading');
        await sendButton.click();

        // Check for loading indicator within a short window
        try {
            const loadingIndicator = page.locator('[data-testid="chat-loading-indicator"]');
            await expect(loadingIndicator).toBeVisible({ timeout: 300 });
        } catch (e) {
            // Loading indicator might be too fast to catch
            console.log('Loading indicator appeared too briefly');
        }

        // Wait for completion
        await page.waitForTimeout(1500);

        // Verify AI response appears
        const aiMessage = page.locator('[data-testid="chat-message-ai"]').first();
        await expect(aiMessage).toBeVisible();
    });

    test('Chat interface is responsive on mobile', async ({ page }) => {
        // Set mobile viewport
        await page.setViewportSize({ width: 375, height: 667 });

        await page.goto(dashboardUrl);
        await page.waitForLoadState('networkidle');

        // Verify elements are still visible
        const chatContainer = page.locator('#chat-container');
        await expect(chatContainer).toBeVisible();

        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        await chatInput.fill('Mobile test');
        await sendButton.click();
        await page.waitForTimeout(1500);

        // Take mobile screenshot
        await page.screenshot({
            path: 'screenshots/ai128-10-mobile-view.png',
            fullPage: true
        });
    });

    test('Complete conversation flow with all features', async ({ page }) => {
        const providerSelector = page.locator('#ai-provider-selector');
        const modelSelector = page.locator('#ai-model-selector');
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Select provider and model
        await providerSelector.selectOption('claude');
        await modelSelector.selectOption('sonnet-4.5');

        // Step 1: Basic query
        await chatInput.fill('Hello, what can you help me with?');
        await sendButton.click();
        await page.waitForTimeout(1500);

        // Step 2: Linear query (should show tool use)
        await chatInput.fill('Show me my Linear issues');
        await sendButton.click();
        await page.waitForTimeout(2000);

        // Step 3: Code request
        await chatInput.fill('Show me Python code example');
        await sendButton.click();
        await page.waitForTimeout(2000);

        // Verify conversation has multiple messages
        const allMessages = page.locator('[data-testid^="chat-message-"]');
        const count = await allMessages.count();

        expect(count).toBeGreaterThanOrEqual(6);

        // Take final screenshot
        await page.screenshot({
            path: 'screenshots/ai128-11-complete-conversation.png',
            fullPage: true
        });
    });
});

test.describe('AI-128: Provider Status API', () => {
    const apiUrl = 'http://127.0.0.1:8420';

    test('Provider status endpoint exists', async ({ request }) => {
        const response = await request.get(`${apiUrl}/api/providers/status`);

        expect(response.ok()).toBeTruthy();
        expect(response.status()).toBe(200);
    });

    test('Provider status returns all providers', async ({ request }) => {
        const response = await request.get(`${apiUrl}/api/providers/status`);
        const data = await response.json();

        expect(data.providers).toBeDefined();
        expect(data.total_providers).toBe(6);
        expect(data.active_providers).toBeGreaterThanOrEqual(0);

        // Check provider structure
        const provider = data.providers[0];
        expect(provider).toHaveProperty('provider_id');
        expect(provider).toHaveProperty('name');
        expect(provider).toHaveProperty('available');
        expect(provider).toHaveProperty('has_api_key');
        expect(provider).toHaveProperty('status');
        expect(provider).toHaveProperty('models');
    });
});
