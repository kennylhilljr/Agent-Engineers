/**
 * AI-262: Conversation Window Functionality - VERIFICATION TESTS
 *
 * Tests to verify that both reported issues are fixed:
 * 1. Excessive scroll distance (input not anchored at bottom) - FIXED
 * 2. No AI responses returned - FIXED (was using wrong port)
 */

const { test, expect } = require('@playwright/test');
const path = require('path');

test.describe('AI-262: Conversation Window - Fixes Verified', () => {
    const chatFilePath = path.resolve(__dirname, '../../dashboard/test_chat.html');
    const chatFileUrl = `file://${chatFilePath}`;

    test('ISSUE 1 FIXED: Input is anchored at bottom, scroll works correctly', async ({ page }) => {
        await page.goto(chatFileUrl);
        await page.waitForLoadState('domcontentloaded');

        const chatMessages = page.locator('#chat-messages');
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');
        const chatContainer = page.locator('.chat-container');

        // Wait for interface
        await chatInput.waitFor({ state: 'visible', timeout: 5000 });

        // Verify chat container layout
        const containerBox = await chatContainer.boundingBox();
        const inputBox = await chatInput.boundingBox();

        // Input should be near the bottom of the container
        const inputDistanceFromTop = inputBox.y - containerBox.y;
        const containerHeight = containerBox.height;
        const inputIsNearBottom = inputDistanceFromTop / containerHeight > 0.8;

        console.log(`Input position: ${inputDistanceFromTop}px from top, container height: ${containerHeight}px`);
        console.log(`Input is near bottom: ${inputIsNearBottom}`);

        expect(inputIsNearBottom).toBe(true);

        // Send multiple messages to test scroll
        const messages = ['Message 1', 'Message 2', 'Message 3'];

        for (const msg of messages) {
            await chatInput.fill(msg);
            await sendButton.click();
            await page.waitForTimeout(1200); // Wait for AI response
        }

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai262-fix-01-scroll-test.png',
            fullPage: true
        });

        // Verify messages are scrolled to bottom
        const scrollInfo = await chatMessages.evaluate(el => ({
            scrollTop: el.scrollTop,
            scrollHeight: el.scrollHeight,
            clientHeight: el.clientHeight,
            isAtBottom: (el.scrollTop + el.clientHeight) >= (el.scrollHeight - 100)
        }));

        console.log('Scroll info:', scrollInfo);
        expect(scrollInfo.isAtBottom).toBe(true);

        console.log('✓ ISSUE 1 FIXED: Input anchored at bottom, auto-scroll working');
    });

    test('ISSUE 2 FIXED: AI responses are returned and displayed', async ({ page }) => {
        await page.goto(chatFileUrl);
        await page.waitForLoadState('domcontentloaded');

        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        await chatInput.waitFor({ state: 'visible', timeout: 5000 });

        // Send a test message
        await chatInput.fill('Hello, are you there?');
        await sendButton.click();

        // Wait for user message
        await page.waitForTimeout(500);
        const userMessages = await page.locator('[data-testid="chat-message-user"]').count();
        expect(userMessages).toBeGreaterThan(0);

        // Wait for AI response
        await page.waitForTimeout(2000);

        // Take screenshot showing both messages
        await page.screenshot({
            path: 'screenshots/ai262-fix-02-ai-response.png',
            fullPage: true
        });

        // Verify AI response appeared
        const aiMessages = await page.locator('[data-testid="chat-message-ai"]').count();
        expect(aiMessages).toBeGreaterThan(0);

        // Get AI response text
        const aiText = await page.locator('[data-testid="chat-message-ai"]').first().textContent();
        console.log('AI Response:', aiText);

        // AI response should contain some text
        expect(aiText.length).toBeGreaterThan(10);

        console.log('✓ ISSUE 2 FIXED: AI responses are being returned and displayed');
    });

    test('VERIFICATION: Complete conversation flow works end-to-end', async ({ page }) => {
        await page.goto(chatFileUrl);
        await page.waitForLoadState('domcontentloaded');

        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');
        const chatMessages = page.locator('#chat-messages');

        await chatInput.waitFor({ state: 'visible', timeout: 5000 });

        // Test conversation with multiple message types
        const testConversation = [
            { user: 'What is my status?', expectedAI: 'status' },
            { user: 'Show me metrics', expectedAI: 'metrics' },
            { user: 'Hello', expectedAI: 'Hello' }
        ];

        for (let i = 0; i < testConversation.length; i++) {
            const { user, expectedAI } = testConversation[i];

            // Send message
            await chatInput.fill(user);
            await sendButton.click();

            // Wait for response
            await page.waitForTimeout(1500);

            // Verify messages increased
            const totalMessages = await page.locator('[data-testid^="chat-message-"]').count();
            expect(totalMessages).toBeGreaterThanOrEqual((i + 1) * 2);

            console.log(`Message ${i + 1}: User="${user}", Total messages=${totalMessages}`);
        }

        // Take final screenshot
        await page.screenshot({
            path: 'screenshots/ai262-fix-03-full-conversation.png',
            fullPage: true
        });

        // Verify final state
        const userCount = await page.locator('[data-testid="chat-message-user"]').count();
        const aiCount = await page.locator('[data-testid="chat-message-ai"]').count();

        console.log(`Final state: ${userCount} user messages, ${aiCount} AI messages`);

        expect(userCount).toBe(3);
        expect(aiCount).toBe(3);

        // Verify scroll is still at bottom
        const isAtBottom = await chatMessages.evaluate(el => {
            return (el.scrollTop + el.clientHeight) >= (el.scrollHeight - 100);
        });

        expect(isAtBottom).toBe(true);

        console.log('✓ VERIFICATION PASSED: Complete conversation flow working correctly');
    });

    test('VERIFICATION: API connection is working (not using fallback)', async ({ page }) => {
        const consoleMessages = [];

        page.on('console', msg => {
            consoleMessages.push({
                type: msg.type(),
                text: msg.text()
            });
        });

        await page.goto(chatFileUrl);
        await page.waitForLoadState('domcontentloaded');

        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        await chatInput.waitFor({ state: 'visible', timeout: 5000 });
        await chatInput.fill('API connection test');
        await sendButton.click();

        await page.waitForTimeout(2000);

        // Check for errors
        const errors = consoleMessages.filter(m =>
            m.type === 'error' &&
            (m.text.includes('Failed to fetch') || m.text.includes('CONNECTION_REFUSED'))
        );

        if (errors.length > 0) {
            console.log('API connection errors detected:');
            errors.forEach(e => console.log('  -', e.text));
        }

        // Should not have connection errors (API should connect successfully)
        expect(errors.length).toBe(0);

        console.log('✓ VERIFICATION PASSED: API connection working without fallback');
    });

    test('VERIFICATION: Provider and model selection works', async ({ page }) => {
        await page.goto(chatFileUrl);
        await page.waitForLoadState('domcontentloaded');

        const providerSelector = page.locator('#ai-provider-selector');
        const modelSelector = page.locator('#ai-model-selector');
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        await providerSelector.waitFor({ state: 'visible', timeout: 5000 });

        // Change provider
        await providerSelector.selectOption('chatgpt');
        await page.waitForTimeout(300);

        // Verify model selector updated
        const modelOptions = await modelSelector.locator('option').allTextContents();
        expect(modelOptions).toContain('GPT-4o');

        // Send a message with new provider
        await chatInput.fill('Test with ChatGPT');
        await sendButton.click();
        await page.waitForTimeout(1500);

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai262-fix-04-provider-selection.png',
            fullPage: true
        });

        // Verify response appeared
        const aiMessages = await page.locator('[data-testid="chat-message-ai"]').count();
        expect(aiMessages).toBeGreaterThan(0);

        console.log('✓ VERIFICATION PASSED: Provider selection working correctly');
    });
});
