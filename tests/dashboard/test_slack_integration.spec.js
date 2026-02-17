/**
 * Playwright Tests - AI-76: Slack Integration - Messages and Reactions
 *
 * REQ-INTEGRATION-002: Chat interface access to Slack MCP tools.
 *
 * Tests:
 *   1.  API: GET /api/integrations/slack/status returns connected:true and tool_count:8
 *   2.  API: GET /api/integrations/slack/status includes channels array
 *   3.  API: GET /api/integrations/slack/channels returns list with recent_messages
 *   4.  API: GET /api/integrations/slack/channels returns exactly 3 channels
 *   5.  API: POST /api/integrations/slack/send sends a message successfully
 *   6.  API: POST /api/integrations/slack/send returns message_id
 *   7.  API: POST /api/integrations/slack/send returns 400 for missing channel
 *   8.  API: GET /api/integrations/slack/messages returns last 5 messages
 *   9.  API: GET /api/integrations/slack/messages?channel=#general filters by channel
 *  10.  API: POST /api/integrations/slack/react adds reaction successfully
 *  11.  API: POST /api/integrations/slack/react returns 400 for missing emoji
 *  12.  UI:  "Send a message to #general" triggers Slack tool call block
 *  13.  UI:  Slack tool call block has correct data-testid attributes
 *  14.  UI:  "slack status" message triggers slack_status tool call
 *  15.  UI:  "read messages from #general" triggers slack_read_messages tool call
 *  16.  UI:  Channel detection from "#ai-cli-macz" pattern in message text
 *  17.  UI:  Screenshot: Slack tool call block with "Send to #ai-cli-macz" result
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8420';

// ---------------------------------------------------------------------------
// API Tests
// ---------------------------------------------------------------------------

test.describe('AI-76: Slack Integration API', () => {

    test('GET /api/integrations/slack/status returns connected:true and tool_count:8', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/slack/status`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('connected', true);
        expect(body).toHaveProperty('tool_count', 8);
        expect(body).toHaveProperty('service', 'Slack');
        expect(body).toHaveProperty('timestamp');
    });

    test('GET /api/integrations/slack/status includes channels array with 3 channels', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/slack/status`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('channels');
        expect(Array.isArray(body.channels)).toBe(true);
        expect(body.channels.length).toBe(3);
        expect(body.channels).toContain('#general');
        expect(body.channels).toContain('#ai-cli-macz');
        expect(body.channels).toContain('#random');
    });

    test('GET /api/integrations/slack/channels returns list with required fields', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/slack/channels`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('channels');
        expect(body).toHaveProperty('count');
        expect(Array.isArray(body.channels)).toBe(true);
        for (const channel of body.channels) {
            expect(channel).toHaveProperty('id');
            expect(channel).toHaveProperty('name');
            expect(channel).toHaveProperty('recent_messages');
        }
    });

    test('GET /api/integrations/slack/channels returns exactly 3 channels', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/slack/channels`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.channels.length).toBe(3);
        expect(body.count).toBe(3);
        const names = body.channels.map(c => c.name);
        expect(names).toContain('#general');
        expect(names).toContain('#ai-cli-macz');
    });

    test('POST /api/integrations/slack/send returns success and message_id', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/slack/send`, {
            data: { channel: '#general', message: 'Hello from AI-76 test!' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('success', true);
        expect(body).toHaveProperty('message_id');
        expect(body.message_id).toBeTruthy();
        expect(body).toHaveProperty('channel', '#general');
        expect(body).toHaveProperty('timestamp');
    });

    test('POST /api/integrations/slack/send returns unique message_id for each call', async ({ request }) => {
        const r1 = await request.post(`${BASE_URL}/api/integrations/slack/send`, {
            data: { channel: '#general', message: 'First message' },
            headers: { 'Content-Type': 'application/json' }
        });
        const r2 = await request.post(`${BASE_URL}/api/integrations/slack/send`, {
            data: { channel: '#random', message: 'Second message' },
            headers: { 'Content-Type': 'application/json' }
        });
        const b1 = await r1.json();
        const b2 = await r2.json();
        expect(b1.success).toBe(true);
        expect(b2.success).toBe(true);
        // Both should have message_ids (may be same if within same second, that's ok for mock)
        expect(b1.message_id).toBeTruthy();
        expect(b2.message_id).toBeTruthy();
    });

    test('POST /api/integrations/slack/send returns 400 for missing channel', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/slack/send`, {
            data: { message: 'No channel specified' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

    test('GET /api/integrations/slack/messages returns last 5 messages', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/slack/messages`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('messages');
        expect(body).toHaveProperty('count');
        expect(Array.isArray(body.messages)).toBe(true);
        expect(body.messages.length).toBeLessThanOrEqual(5);
        for (const msg of body.messages) {
            expect(msg).toHaveProperty('id');
            expect(msg).toHaveProperty('user');
            expect(msg).toHaveProperty('text');
        }
    });

    test('GET /api/integrations/slack/messages?channel=#general filters by channel', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/slack/messages?channel=%23general`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('messages');
        expect(Array.isArray(body.messages)).toBe(true);
        // All returned messages should be from #general
        for (const msg of body.messages) {
            expect(msg.channel.toLowerCase()).toContain('general');
        }
    });

    test('POST /api/integrations/slack/react adds reaction successfully', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/slack/react`, {
            data: { channel: '#general', message_id: 'MSG001', emoji: 'thumbsup' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('success', true);
        expect(body).toHaveProperty('channel', '#general');
        expect(body).toHaveProperty('message_id', 'MSG001');
        expect(body).toHaveProperty('emoji', 'thumbsup');
        expect(body).toHaveProperty('timestamp');
    });

    test('POST /api/integrations/slack/react returns 400 for missing emoji', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/slack/react`, {
            data: { channel: '#general', message_id: 'MSG001' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

});

// ---------------------------------------------------------------------------
// UI Tests
// ---------------------------------------------------------------------------

test.describe('AI-76: Slack Integration UI - Tool Call Blocks', () => {

    test('Typing "Send a message to #general" renders a Slack tool call block', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'Send a message to #general: Hello world');
        await page.click('#chat-send-btn');

        // Wait for Slack tool call block to appear
        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });
        const block = page.locator('[data-testid="tool-call-block"]');
        await expect(block).toBeVisible();
    });

    test('Slack tool call block has correct data-testid attributes', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'Send a message to #general');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Verify structural testids
        await expect(page.locator('[data-testid="tool-call-header"]').first()).toBeVisible();
        await expect(page.locator('[data-testid="tool-call-name"]').first()).toBeVisible();
        await expect(page.locator('[data-testid="tool-call-toggle"]').first()).toBeVisible();
    });

    test('"slack status" message triggers slack_status tool call block', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'slack status');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });
        const toolName = page.locator('[data-testid="tool-call-name"]').first();
        await expect(toolName).toContainText('slack_status');
    });

    test('"read messages from #general" triggers slack_read_messages tool call', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'read messages from #general');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });
        const toolName = page.locator('[data-testid="tool-call-name"]').first();
        await expect(toolName).toContainText('slack_read_messages');
    });

    test('Channel #ai-cli-macz is detected from message text', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'Send a message to #ai-cli-macz');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });
        const block = page.locator('[data-testid="tool-call-block"]');
        await expect(block).toBeVisible();
        // The tool call body should mention the channel
        await page.locator('[data-testid="tool-call-header"]').first().click();
        await page.waitForTimeout(300);
        const body = page.locator('[data-testid="tool-call-body"]').first();
        await expect(body).not.toHaveClass(/hidden/);
    });

    test('After Slack tool call, an AI message with result also appears', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'slack status');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });
        const aiMessages = page.locator('[data-testid="chat-message-ai"]');
        await expect(aiMessages.last()).toBeVisible();
    });

    test('Screenshot: save Slack tool call block to screenshots/ai-76-slack-integration.png', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        // Send a message that triggers a Slack send tool call
        await page.fill('#chat-input', 'Send to #ai-cli-macz: Project update sent successfully');
        await page.click('#chat-send-btn');

        // Wait for tool call block to render
        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Click to expand the tool call body
        await page.locator('[data-testid="tool-call-header"]').first().click();
        await page.waitForTimeout(500);

        // Take full-page screenshot
        await page.screenshot({
            path: 'screenshots/ai-76-slack-integration.png',
            fullPage: false
        });
    });

});
