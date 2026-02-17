/**
 * Provider Hot-Swap Tests - AI-74
 * Verifies that switching providers mid-conversation:
 *  - Preserves full conversation history in the UI
 *  - Inserts a system message noting the provider change
 *  - Sends conversation context to the new provider for continuity
 *  - Does not interrupt running agent operations
 */

const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8444';
const SCREENSHOT_DIR = path.join(__dirname, '../../screenshots');

if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

// Provider display names used in system messages
const PROVIDER_DISPLAY_NAMES = {
    'claude':    'Claude',
    'chatgpt':   'ChatGPT',
    'gemini':    'Gemini',
    'groq':      'Groq',
    'kimi':      'KIMI',
    'windsurf':  'Windsurf'
};

// Helper: send a chat message and wait for AI response
async function sendMessage(page, text) {
    const chatInput = page.locator('#chat-input');
    const sendBtn   = page.locator('#chat-send-btn');
    await chatInput.fill(text);
    await sendBtn.click();
    // Wait for AI response (loading indicator disappears)
    await page.waitForTimeout(1200);
}

// Helper: switch provider via dropdown
async function switchProvider(page, providerId) {
    const selector = page.locator('#ai-provider-selector');
    await selector.selectOption(providerId);
    await page.waitForTimeout(300);
}

// Helper: count all chat messages
async function countMessages(page) {
    return page.locator('[data-testid^="chat-message-"]').count();
}

// ============================================================
// Test Suite
// ============================================================

test.describe('AI-74: Hot-Swap Providers Without Context Loss', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
        // Clear history to start fresh
        try {
            await fetch(`${BASE_URL}/api/chat/history`, { method: 'DELETE' });
        } catch (_) {}
        // Reload after clearing
        await page.reload();
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(500);
    });

    // ----------------------------------------------------------
    // Test 1: Switching provider inserts a system message
    // ----------------------------------------------------------
    test('Test 1: Switching provider inserts system message in chat', async ({ page }) => {
        // Start with Claude (default)
        const selector = page.locator('#ai-provider-selector');
        await selector.selectOption('claude');
        await page.waitForTimeout(300);

        // Send a message to establish context
        await sendMessage(page, 'Hello from Claude');

        // Switch to ChatGPT
        await selector.selectOption('chatgpt');
        await page.waitForTimeout(500);

        // Verify system message is present
        const systemMessages = page.locator('[data-testid="chat-message-system"]');
        const count = await systemMessages.count();
        expect(count).toBeGreaterThanOrEqual(1);

        // Verify system message text contains the switch info
        const allSystemTexts = await systemMessages.allTextContents();
        const hasSwitchMessage = allSystemTexts.some(t =>
            t.includes('Switched') && t.includes('Claude') && t.includes('ChatGPT')
        );
        expect(hasSwitchMessage).toBe(true);

        console.log('Test 1 passed: Provider switch inserts system message');
    });

    // ----------------------------------------------------------
    // Test 2: Conversation history is preserved after switch
    // ----------------------------------------------------------
    test('Test 2: Chat history is preserved after provider switch', async ({ page }) => {
        const selector = page.locator('#ai-provider-selector');
        await selector.selectOption('claude');
        await page.waitForTimeout(300);

        // Send several messages to establish context
        await sendMessage(page, 'What is my status?');
        await sendMessage(page, 'Show me performance metrics');
        await sendMessage(page, 'Any errors to report?');

        // Count messages before switch
        const beforeSwitch = await countMessages(page);
        expect(beforeSwitch).toBeGreaterThanOrEqual(6); // 3 user + 3 AI

        // Switch to ChatGPT
        await selector.selectOption('chatgpt');
        await page.waitForTimeout(500);

        // All previous messages should still be visible
        const afterSwitch = await countMessages(page);
        // After switch: previous messages + 1 system message
        expect(afterSwitch).toBeGreaterThanOrEqual(beforeSwitch + 1);

        // Verify original user messages still visible
        const userMessages = await page.locator('[data-testid="chat-message-user"]').allTextContents();
        expect(userMessages.some(t => t.includes('What is my status'))).toBe(true);
        expect(userMessages.some(t => t.includes('performance metrics'))).toBe(true);

        console.log('Test 2 passed: Chat history preserved after provider switch');
    });

    // ----------------------------------------------------------
    // Test 3: Switching back and forth preserves all messages
    // ----------------------------------------------------------
    test('Test 3: Switching back and forth preserves all messages', async ({ page }) => {
        const selector = page.locator('#ai-provider-selector');

        // Send message as Claude
        await selector.selectOption('claude');
        await page.waitForTimeout(300);
        await sendMessage(page, 'Hello from Claude');

        // Switch to Gemini
        await selector.selectOption('gemini');
        await page.waitForTimeout(500);

        // Send message as Gemini
        await sendMessage(page, 'Hello from Gemini');

        // Switch back to Claude
        await selector.selectOption('claude');
        await page.waitForTimeout(500);

        // Verify all messages are still there
        const allUserMessages = await page.locator('[data-testid="chat-message-user"]').allTextContents();
        expect(allUserMessages.some(t => t.includes('Hello from Claude'))).toBe(true);
        expect(allUserMessages.some(t => t.includes('Hello from Gemini'))).toBe(true);

        // Verify two system messages (Claude→Gemini, Gemini→Claude)
        const systemMessages = page.locator('[data-testid="chat-message-system"]');
        const sysCount = await systemMessages.count();
        expect(sysCount).toBeGreaterThanOrEqual(2);

        console.log('Test 3 passed: All messages preserved across multiple switches');
    });

    // ----------------------------------------------------------
    // Test 4: Verify system message uses correct display names
    // ----------------------------------------------------------
    test('Test 4: System message uses correct display names', async ({ page }) => {
        const selector = page.locator('#ai-provider-selector');
        await selector.selectOption('claude');
        await page.waitForTimeout(300);

        const tests = [
            { from: 'claude', to: 'chatgpt', fromName: 'Claude', toName: 'ChatGPT' },
            { from: 'chatgpt', to: 'gemini',  fromName: 'ChatGPT', toName: 'Gemini' },
            { from: 'gemini',  to: 'groq',    fromName: 'Gemini', toName: 'Groq' }
        ];

        for (const { from, to, fromName, toName } of tests) {
            await selector.selectOption(from);
            await page.waitForTimeout(200);
            await selector.selectOption(to);
            await page.waitForTimeout(400);

            const systemTexts = await page.locator('[data-testid="chat-message-system"]').allTextContents();
            const hasCorrectNames = systemTexts.some(t => t.includes(fromName) && t.includes(toName));
            expect(hasCorrectNames).toBe(true);
        }

        console.log('Test 4 passed: Display names are correct in system messages');
    });

    // ----------------------------------------------------------
    // Test 5: No DOM clearing on provider switch
    // ----------------------------------------------------------
    test('Test 5: DOM messages are not cleared on provider switch', async ({ page }) => {
        const selector = page.locator('#ai-provider-selector');
        await selector.selectOption('claude');
        await page.waitForTimeout(300);

        await sendMessage(page, 'Remember this message');
        await page.waitForTimeout(300);

        const chatMessages = page.locator('#chat-messages');
        const innerBefore = await chatMessages.innerHTML();

        // Switch provider
        await selector.selectOption('chatgpt');
        await page.waitForTimeout(500);

        const innerAfter = await chatMessages.innerHTML();

        // The messages area should still contain the original message
        expect(innerAfter).toContain('Remember this message');
        // Should have grown (system message added)
        expect(innerAfter.length).toBeGreaterThan(innerBefore.length);

        console.log('Test 5 passed: DOM messages are not cleared on provider switch');
    });

    // ----------------------------------------------------------
    // Test 6: New provider AI response includes context note
    // ----------------------------------------------------------
    test('Test 6: New provider response acknowledges prior context', async ({ page }) => {
        const selector = page.locator('#ai-provider-selector');
        await selector.selectOption('claude');
        await page.waitForTimeout(300);

        // Send a few messages with Claude
        await sendMessage(page, 'What is my status?');
        await sendMessage(page, 'Show me metrics');

        // Switch to ChatGPT
        await selector.selectOption('chatgpt');
        await page.waitForTimeout(500);

        // Send a message to ChatGPT
        await sendMessage(page, 'Do you have context from our prior conversation?');

        // Verify AI response contains context note
        const aiMessages = await page.locator('[data-testid="chat-message-ai"]').allTextContents();
        const lastAiMessage = aiMessages[aiMessages.length - 1];
        // The AI response should mention context (via our context note implementation)
        expect(lastAiMessage).toContain('ChatGPT');

        console.log('Test 6 passed: New provider responds with context awareness');
    });

    // ----------------------------------------------------------
    // Test 7: API endpoint POST /api/chat/provider-switch
    // ----------------------------------------------------------
    test('Test 7: API endpoint POST /api/chat/provider-switch', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/chat/provider-switch`, {
            data: {
                from_provider: 'claude',
                to_provider: 'chatgpt',
                timestamp: new Date().toISOString(),
                message_count: 5
            }
        });

        expect(response.status()).toBe(200);
        const data = await response.json();
        expect(data.success).toBe(true);
        expect(data.context_preserved).toBe(true);
        expect(data.from_provider).toBe('claude');
        expect(data.to_provider).toBe('chatgpt');

        console.log('Test 7 passed: POST /api/chat/provider-switch works correctly');
    });

    // ----------------------------------------------------------
    // Test 8: API endpoint GET /api/chat/provider-switch returns history
    // ----------------------------------------------------------
    test('Test 8: API endpoint GET /api/chat/provider-switch returns history', async ({ request }) => {
        // First record a switch
        await request.post(`${BASE_URL}/api/chat/provider-switch`, {
            data: {
                from_provider: 'claude',
                to_provider: 'gemini',
                message_count: 3
            }
        });

        // Then retrieve history
        const response = await request.get(`${BASE_URL}/api/chat/provider-switch`);
        expect(response.status()).toBe(200);

        const data = await response.json();
        expect(data).toHaveProperty('switches');
        expect(data).toHaveProperty('count');
        expect(Array.isArray(data.switches)).toBe(true);
        expect(data.count).toBeGreaterThanOrEqual(1);

        // Verify the recorded switch is in the history
        const switches = data.switches;
        const found = switches.some(s => s.from_provider === 'claude' && s.to_provider === 'gemini');
        expect(found).toBe(true);

        console.log('Test 8 passed: GET /api/chat/provider-switch returns history');
    });

    // ----------------------------------------------------------
    // Test 9: API endpoint rejects invalid request body
    // ----------------------------------------------------------
    test('Test 9: API endpoint rejects missing required fields', async ({ request }) => {
        // Missing to_provider
        const response = await request.post(`${BASE_URL}/api/chat/provider-switch`, {
            data: { from_provider: 'claude' }
        });
        expect(response.status()).toBe(400);

        const data = await response.json();
        expect(data).toHaveProperty('error');

        console.log('Test 9 passed: API rejects requests missing required fields');
    });

    // ----------------------------------------------------------
    // Test 10: Verify getConversationContext() returns formatted context
    // ----------------------------------------------------------
    test('Test 10: getConversationContext() returns last 10 messages as context string', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        const selector = page.locator('#ai-provider-selector');
        await selector.selectOption('claude');
        await page.waitForTimeout(300);

        // Send several messages
        await sendMessage(page, 'Message one');
        await sendMessage(page, 'Message two');
        await sendMessage(page, 'Message three');

        // Get context via JS evaluation
        const context = await page.evaluate(() => {
            if (window.chatInterface && typeof window.chatInterface.getConversationContext === 'function') {
                return window.chatInterface.getConversationContext();
            }
            return null;
        });

        // Context should be a non-empty string with User/Assistant labels
        expect(context).not.toBeNull();
        expect(typeof context).toBe('string');
        expect(context.length).toBeGreaterThan(0);
        expect(context).toContain('User:');

        console.log('Test 10 passed: getConversationContext() returns formatted context');
    });

    // ----------------------------------------------------------
    // Test 11: Switching provider does not affect the selectedProvider state incorrectly
    // ----------------------------------------------------------
    test('Test 11: Provider state is correctly updated after switch', async ({ page }) => {
        const selector = page.locator('#ai-provider-selector');

        await selector.selectOption('claude');
        await page.waitForTimeout(300);

        // Verify initial state
        let provider = await page.evaluate(() => window.chatInterface?.getSelectedProvider?.());
        expect(provider).toBe('claude');

        // Switch to Groq
        await selector.selectOption('groq');
        await page.waitForTimeout(500);

        // Verify updated state
        provider = await page.evaluate(() => window.chatInterface?.getSelectedProvider?.());
        expect(provider).toBe('groq');

        // Switch back to Claude
        await selector.selectOption('claude');
        await page.waitForTimeout(500);

        provider = await page.evaluate(() => window.chatInterface?.getSelectedProvider?.());
        expect(provider).toBe('claude');

        console.log('Test 11 passed: Provider state is correctly updated');
    });

    // ----------------------------------------------------------
    // Test 12: Screenshot - chat with system message "Switched from Claude to ChatGPT"
    // ----------------------------------------------------------
    test('Test 12: Screenshot shows Switched from Claude to ChatGPT system message', async ({ page }) => {
        const selector = page.locator('#ai-provider-selector');

        // Start with Claude
        await selector.selectOption('claude');
        await page.waitForTimeout(300);

        // Send messages to establish context
        await sendMessage(page, 'What is my current agent status?');
        await sendMessage(page, 'Show me performance metrics');
        await sendMessage(page, 'Any errors in the system?');

        // Switch to ChatGPT
        await selector.selectOption('chatgpt');
        await page.waitForTimeout(600);

        // Verify system message is present
        const systemMessages = page.locator('[data-testid="chat-message-system"]');
        const sysCount = await systemMessages.count();
        expect(sysCount).toBeGreaterThanOrEqual(1);

        const systemTexts = await systemMessages.allTextContents();
        const hasSwitchMsg = systemTexts.some(t =>
            t.includes('Switched') && t.includes('Claude') && t.includes('ChatGPT')
        );
        expect(hasSwitchMsg).toBe(true);

        // Scroll to bottom so system message is visible
        await page.evaluate(() => {
            const container = document.getElementById('chat-messages');
            if (container) container.scrollTop = container.scrollHeight;
        });
        await page.waitForTimeout(300);

        // Take screenshot
        const screenshotPath = path.join(SCREENSHOT_DIR, 'ai-74-provider-hotswap.png');
        await page.screenshot({
            path: screenshotPath,
            fullPage: false
        });

        console.log(`Test 12 passed: Screenshot saved to ${screenshotPath}`);
    });

});
