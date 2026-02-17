/**
 * Playwright Tests - AI-133: Message History Persistence (REQ-CHAT-002)
 *
 * Tests:
 *   API:
 *     1. GET  /api/chat/history - returns empty history on fresh server
 *     2. POST /api/chat/history - append a single user message
 *     3. POST /api/chat/history - append an ai message
 *     4. POST /api/chat/history - append a system message
 *     5. POST /api/chat/history - returns 400 for missing required fields
 *     6. POST /api/chat/history - returns 400 for invalid type
 *     7. GET  /api/chat/history - returns all persisted messages
 *     8. DELETE /api/chat/history - clears all messages
 *     9. GET  /api/chat/history - returns empty after DELETE
 *    10. POST /api/chat/history - accepts an array of messages
 *    11. Large history: 100+ messages performance test
 *
 *   UI:
 *    12. Clear History button is visible in chat header
 *    13. Messages survive page refresh (localStorage + API)
 *    14. Timestamps display correctly (HH:MM format)
 *    15. User message type persists correctly
 *    16. AI message type persists correctly
 *    17. System messages are rendered with correct class
 *    18. Clear History button clears chat UI and API
 *    19. History count label updates on send
 *    20. History persists after multiple page refreshes
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8436';

// ---------------------------------------------------------------------------
// Helper: clear history before each test to ensure isolation
// ---------------------------------------------------------------------------

async function clearHistory(request) {
    await request.delete(`${BASE_URL}/api/chat/history`);
}

// ---------------------------------------------------------------------------
// API Tests
// ---------------------------------------------------------------------------

test.describe('AI-133: Chat History API', () => {

    test.beforeEach(async ({ request }) => {
        await clearHistory(request);
    });

    test('GET /api/chat/history returns empty list on fresh state', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/chat/history`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('messages');
        expect(Array.isArray(body.messages)).toBe(true);
        expect(body.messages.length).toBe(0);
        expect(body).toHaveProperty('count', 0);
        expect(body).toHaveProperty('timestamp');
    });

    test('POST /api/chat/history appends a user message', async ({ request }) => {
        const msg = {
            id: 1001,
            type: 'user',
            content: 'Hello from test',
            timestamp: new Date().toISOString(),
            provider: 'claude',
            model: 'haiku-4.5'
        };
        const response = await request.post(`${BASE_URL}/api/chat/history`, {
            data: msg,
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('added', 1);
        expect(body).toHaveProperty('total', 1);
    });

    test('POST /api/chat/history appends an ai message', async ({ request }) => {
        const msg = {
            id: 1002,
            type: 'ai',
            content: 'AI response text',
            timestamp: new Date().toISOString(),
            provider: 'claude',
            model: 'haiku-4.5'
        };
        const response = await request.post(`${BASE_URL}/api/chat/history`, {
            data: msg,
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.added).toBe(1);
    });

    test('POST /api/chat/history appends a system message', async ({ request }) => {
        const msg = {
            id: 1003,
            type: 'system',
            content: 'Agent status changed to idle',
            timestamp: new Date().toISOString()
        };
        const response = await request.post(`${BASE_URL}/api/chat/history`, {
            data: msg,
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.added).toBe(1);
    });

    test('POST /api/chat/history returns 400 for missing content field', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/chat/history`, {
            data: { id: 999, type: 'user' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

    test('POST /api/chat/history returns 400 for invalid message type', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/chat/history`, {
            data: { id: 999, type: 'invalid_type', content: 'test' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

    test('GET /api/chat/history returns all persisted messages', async ({ request }) => {
        // Post 3 messages
        const messages = [
            { id: 2001, type: 'user', content: 'Message one', timestamp: new Date().toISOString() },
            { id: 2002, type: 'ai',   content: 'AI reply one', timestamp: new Date().toISOString() },
            { id: 2003, type: 'user', content: 'Message two', timestamp: new Date().toISOString() }
        ];

        for (const msg of messages) {
            await request.post(`${BASE_URL}/api/chat/history`, {
                data: msg,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        const response = await request.get(`${BASE_URL}/api/chat/history`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.messages.length).toBe(3);
        expect(body.count).toBe(3);

        // Verify message contents
        expect(body.messages[0].content).toBe('Message one');
        expect(body.messages[0].type).toBe('user');
        expect(body.messages[1].content).toBe('AI reply one');
        expect(body.messages[1].type).toBe('ai');
        expect(body.messages[2].content).toBe('Message two');
    });

    test('DELETE /api/chat/history clears all messages', async ({ request }) => {
        // Add messages first
        await request.post(`${BASE_URL}/api/chat/history`, {
            data: { id: 3001, type: 'user', content: 'To be deleted', timestamp: new Date().toISOString() },
            headers: { 'Content-Type': 'application/json' }
        });

        // Delete history
        const deleteResponse = await request.delete(`${BASE_URL}/api/chat/history`);
        expect(deleteResponse.status()).toBe(200);
        const deleteBody = await deleteResponse.json();
        expect(deleteBody).toHaveProperty('status', 'ok');
        expect(deleteBody).toHaveProperty('cleared');
        expect(deleteBody.cleared).toBeGreaterThanOrEqual(1);
    });

    test('GET /api/chat/history returns empty list after DELETE', async ({ request }) => {
        // Add messages
        await request.post(`${BASE_URL}/api/chat/history`, {
            data: { id: 4001, type: 'user', content: 'Message before clear', timestamp: new Date().toISOString() },
            headers: { 'Content-Type': 'application/json' }
        });

        // Clear
        await request.delete(`${BASE_URL}/api/chat/history`);

        // Verify empty
        const response = await request.get(`${BASE_URL}/api/chat/history`);
        const body = await response.json();
        expect(body.messages.length).toBe(0);
        expect(body.count).toBe(0);
    });

    test('POST /api/chat/history accepts an array of messages', async ({ request }) => {
        const batch = [
            { id: 5001, type: 'user', content: 'Batch msg 1', timestamp: new Date().toISOString() },
            { id: 5002, type: 'ai',   content: 'Batch AI 1',  timestamp: new Date().toISOString() },
            { id: 5003, type: 'system', content: 'System notice', timestamp: new Date().toISOString() }
        ];

        const response = await request.post(`${BASE_URL}/api/chat/history`, {
            data: batch,
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.added).toBe(3);
        expect(body.total).toBe(3);
    });

    test('Large history: 100+ messages performance test', async ({ request }) => {
        const messages = [];
        for (let i = 0; i < 105; i++) {
            messages.push({
                id: 6000 + i,
                type: i % 2 === 0 ? 'user' : 'ai',
                content: `Performance test message ${i}`,
                timestamp: new Date().toISOString()
            });
        }

        // Post in batches of 10
        const start = Date.now();
        for (let i = 0; i < messages.length; i += 10) {
            const batch = messages.slice(i, i + 10);
            await request.post(`${BASE_URL}/api/chat/history`, {
                data: batch,
                headers: { 'Content-Type': 'application/json' }
            });
        }
        const elapsed = Date.now() - start;

        // Should complete within 5 seconds
        expect(elapsed).toBeLessThan(5000);

        // Verify we can GET all 105 messages
        const response = await request.get(`${BASE_URL}/api/chat/history`);
        const body = await response.json();
        expect(body.messages.length).toBe(105);
        expect(body.count).toBe(105);
    });

});

// ---------------------------------------------------------------------------
// UI Tests
// ---------------------------------------------------------------------------

test.describe('AI-133: Chat History UI', () => {

    test.beforeEach(async ({ request, page }) => {
        // Clear API history
        await clearHistory(request);
        // Navigate to dashboard and clear localStorage
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
        await page.evaluate(() => {
            localStorage.removeItem('agent_dashboard_chat_history');
        });
        // Reload to start fresh
        await page.reload();
        await page.waitForLoadState('networkidle');
    });

    test('Clear History button is visible in chat header', async ({ page }) => {
        const clearBtn = page.locator('[data-testid="clear-history-button"]');
        await expect(clearBtn).toBeVisible();
        const btnText = await clearBtn.textContent();
        expect(btnText).toContain('Clear History');
    });

    test('History count label is visible in chat toolbar', async ({ page }) => {
        const countLabel = page.locator('[data-testid="chat-history-count"]');
        await expect(countLabel).toBeVisible();
    });

    test('History count label updates after sending a message', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendBtn = page.locator('#chat-send-btn');
        const countLabel = page.locator('[data-testid="chat-history-count"]');

        // Verify starts at 0
        const initialText = await countLabel.textContent();
        expect(initialText).toContain('0');

        // Send a message
        await chatInput.fill('Hello test message');
        await sendBtn.click();
        await page.waitForTimeout(600);

        // Count should have increased
        const afterText = await countLabel.textContent();
        expect(afterText).not.toContain('0 messages');
    });

    test('User message is rendered correctly after send', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendBtn = page.locator('#chat-send-btn');

        await chatInput.fill('Test user message');
        await sendBtn.click();
        await page.waitForTimeout(500);

        const userMsg = page.locator('[data-testid="chat-message-user"]').first();
        await expect(userMsg).toBeVisible();
        const content = await userMsg.textContent();
        expect(content).toContain('Test user message');
    });

    test('AI message is rendered correctly after send', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendBtn = page.locator('#chat-send-btn');

        await chatInput.fill('Hello AI');
        await sendBtn.click();
        // Wait for AI simulated response (800ms delay in sendMessage)
        await page.waitForTimeout(1200);

        const aiMessages = page.locator('[data-testid="chat-message-ai"]');
        const count = await aiMessages.count();
        expect(count).toBeGreaterThan(0);
    });

    test('Timestamps display correctly (HH:MM format)', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendBtn = page.locator('#chat-send-btn');

        await chatInput.fill('Message with timestamp');
        await sendBtn.click();
        await page.waitForTimeout(500);

        const timestamp = page.locator('.chat-timestamp').first();
        await expect(timestamp).toBeVisible();
        const timeText = await timestamp.textContent();
        // Should match HH:MM or H:MM format
        expect(timeText).toMatch(/\d{1,2}:\d{2}/);
    });

    test('Messages survive page refresh (localStorage + API persistence)', async ({ request, page }) => {
        const chatInput = page.locator('#chat-input');
        const sendBtn = page.locator('#chat-send-btn');

        // Send messages
        await chatInput.fill('Persist message alpha');
        await sendBtn.click();
        await page.waitForTimeout(600);

        await chatInput.fill('Persist message beta');
        await sendBtn.click();
        await page.waitForTimeout(600);

        const beforeCount = await page.locator('[data-testid="chat-message-user"]').count();
        expect(beforeCount).toBeGreaterThanOrEqual(2);

        // Refresh page
        await page.reload();
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(1000);

        // Messages should be restored
        const afterCount = await page.locator('[data-testid="chat-message-user"]').count();
        expect(afterCount).toBeGreaterThanOrEqual(beforeCount);

        // Verify specific message content
        const allContents = await page.locator('[data-testid="chat-message-user"]').allTextContents();
        const hasAlpha = allContents.some(t => t.includes('Persist message alpha'));
        const hasBeta = allContents.some(t => t.includes('Persist message beta'));
        expect(hasAlpha).toBe(true);
        expect(hasBeta).toBe(true);
    });

    test('Clear History button clears chat UI and API history', async ({ request, page }) => {
        const chatInput = page.locator('#chat-input');
        const sendBtn = page.locator('#chat-send-btn');
        const clearBtn = page.locator('[data-testid="clear-history-button"]');

        // Send some messages and wait for AI response (800ms delay)
        await chatInput.fill('Message to be cleared');
        await sendBtn.click();
        await page.waitForTimeout(1200);

        // Verify messages are there (user + AI)
        const beforeCount = await page.locator('[data-testid="chat-message-user"]').count();
        expect(beforeCount).toBeGreaterThan(0);

        // Click clear history and wait for async clear to complete
        await clearBtn.click();
        await page.waitForTimeout(800);

        // Chat UI should be cleared - no user or ai messages remain
        const afterCount = await page.locator('[data-testid="chat-message-user"]').count();
        expect(afterCount).toBe(0);

        const afterAiCount = await page.locator('[data-testid="chat-message-ai"]').count();
        expect(afterAiCount).toBe(0);

        // History count label should show 0
        const countLabel = page.locator('[data-testid="chat-history-count"]');
        const labelText = await countLabel.textContent();
        expect(labelText).toContain('0');

        // API should also be cleared
        const apiResp = await request.get(`${BASE_URL}/api/chat/history`);
        const apiBody = await apiResp.json();
        expect(apiBody.count).toBe(0);
    });

    test('History persists after multiple page refreshes', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendBtn = page.locator('#chat-send-btn');

        // Send initial messages
        await chatInput.fill('Multi-refresh test message');
        await sendBtn.click();
        await page.waitForTimeout(600);

        const initialCount = await page.locator('[data-testid="chat-message-user"]').count();
        expect(initialCount).toBeGreaterThanOrEqual(1);

        // Refresh twice
        for (let i = 0; i < 2; i++) {
            await page.reload();
            await page.waitForLoadState('networkidle');
            await page.waitForTimeout(1000);

            const count = await page.locator('[data-testid="chat-message-user"]').count();
            expect(count).toBeGreaterThanOrEqual(initialCount);
        }

        // Verify the specific message content
        const allContents = await page.locator('[data-testid="chat-message-user"]').allTextContents();
        const hasMsg = allContents.some(t => t.includes('Multi-refresh test message'));
        expect(hasMsg).toBe(true);
    });

    test('Message data-message-id attribute is set correctly', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendBtn = page.locator('#chat-send-btn');

        await chatInput.fill('Metadata test message');
        await sendBtn.click();
        await page.waitForTimeout(500);

        const message = page.locator('[data-testid="chat-message-user"]').first();
        const msgId = await message.getAttribute('data-message-id');
        expect(msgId).toBeTruthy();
        expect(parseInt(msgId)).toBeGreaterThan(0);
    });

    test('System message type can be rendered with correct class', async ({ page }) => {
        // Inject a system message directly via the chat interface JS API
        await page.evaluate(() => {
            if (window.chatInterface) {
                window.chatInterface.addMessage('System: Agent status changed', 'system');
            }
        });
        await page.waitForTimeout(400);

        const systemMsg = page.locator('[data-testid="chat-message-system"]');
        const count = await systemMsg.count();
        expect(count).toBeGreaterThan(0);
    });

    test('Large history: 100+ messages display without performance issues', async ({ request, page }) => {
        // Pre-populate API with 100 messages
        const messages = [];
        for (let i = 0; i < 100; i++) {
            messages.push({
                id: 9000 + i,
                type: i % 2 === 0 ? 'user' : 'ai',
                content: `Large history message ${i}: Lorem ipsum dolor sit amet.`,
                timestamp: new Date(Date.now() - (100 - i) * 1000).toISOString()
            });
        }

        // Batch upload
        for (let i = 0; i < messages.length; i += 20) {
            await request.post(`${BASE_URL}/api/chat/history`, {
                data: messages.slice(i, i + 20),
                headers: { 'Content-Type': 'application/json' }
            });
        }

        // Load page - should restore history quickly
        const loadStart = Date.now();
        await page.reload();
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(1500);
        const loadTime = Date.now() - loadStart;

        // Should load within 5 seconds
        expect(loadTime).toBeLessThan(5000);

        // Should render messages
        const messageCount = await page.locator('[data-testid^="chat-message-"]').count();
        expect(messageCount).toBeGreaterThanOrEqual(50); // At least half should be visible
    });

});
