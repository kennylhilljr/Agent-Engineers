/**
 * Playwright Tests - AI-78: Tool Transparency - Collapsible Tool Call Details
 *
 * Tests:
 *   1.  API: POST /api/tools/call records a tool call and returns 200
 *   2.  API: POST /api/tools/call rejects missing tool_name with 400
 *   3.  API: POST /api/tools/call rejects invalid status with 400
 *   4.  API: GET /api/tools/calls returns list of recorded calls
 *   5.  API: DELETE /api/tools/calls clears history
 *   6.  API: POST /api/tools/call stores duration_ms and status correctly
 *   7.  UI:  Tool call block shows duration in header
 *   8.  UI:  Tool call block shows success checkmark for success status
 *   9.  UI:  Tool call block shows error status with red highlight class
 *  10.  UI:  Tool call block body is collapsible (toggles hidden)
 *  11.  UI:  Multiple tool calls from one message all show in chat
 *  12.  UI:  data-status attribute reflects success/error correctly
 *  13.  API: POST /api/tools/call with error status records correctly
 *  14.  UI:  Sending "linear status" message shows tool call block with duration
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8450';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function clearToolCalls(request) {
    await request.delete(`${BASE_URL}/api/tools/calls`);
}

// ---------------------------------------------------------------------------
// API Tests
// ---------------------------------------------------------------------------

test.describe('AI-78: Tool Call History API', () => {

    test.beforeEach(async ({ request }) => {
        await clearToolCalls(request);
    });

    test('POST /api/tools/call records a success call and returns 200', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/tools/call`, {
            data: {
                tool_name: 'linear_get_issue',
                input: { issue_key: 'AI-1' },
                result: 'AI-1 is "In Progress"',
                duration_ms: 42,
                status: 'success'
            }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('entry');
        expect(body.entry).toHaveProperty('tool_name', 'linear_get_issue');
        expect(body.entry).toHaveProperty('duration_ms', 42);
        expect(body.entry).toHaveProperty('status', 'success');
    });

    test('POST /api/tools/call rejects request with missing tool_name with 400', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/tools/call`, {
            data: {
                input: {},
                result: 'something',
                status: 'success'
            }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
        expect(body.error).toMatch(/tool_name/i);
    });

    test('POST /api/tools/call rejects invalid status value with 400', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/tools/call`, {
            data: {
                tool_name: 'test_tool',
                status: 'unknown'
            }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
        expect(body.error).toMatch(/success.*error|error.*success/i);
    });

    test('GET /api/tools/calls returns list of recorded calls with count', async ({ request }) => {
        // Post two tool calls
        await request.post(`${BASE_URL}/api/tools/call`, {
            data: { tool_name: 'tool_a', input: {}, result: 'ok', status: 'success', duration_ms: 10 }
        });
        await request.post(`${BASE_URL}/api/tools/call`, {
            data: { tool_name: 'tool_b', input: {}, result: 'failed', status: 'error', duration_ms: 5 }
        });

        const response = await request.get(`${BASE_URL}/api/tools/calls`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('calls');
        expect(body).toHaveProperty('count');
        expect(Array.isArray(body.calls)).toBe(true);
        expect(body.count).toBeGreaterThanOrEqual(2);
        const names = body.calls.map(c => c.tool_name);
        expect(names).toContain('tool_a');
        expect(names).toContain('tool_b');
    });

    test('DELETE /api/tools/calls clears history and returns cleared count', async ({ request }) => {
        // Post a call first
        await request.post(`${BASE_URL}/api/tools/call`, {
            data: { tool_name: 'temp_tool', input: {}, result: 'x', status: 'success' }
        });

        const deleteResp = await request.delete(`${BASE_URL}/api/tools/calls`);
        expect(deleteResp.status()).toBe(200);
        const body = await deleteResp.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('cleared');
        expect(body.cleared).toBeGreaterThanOrEqual(1);

        // Verify cleared
        const getResp = await request.get(`${BASE_URL}/api/tools/calls`);
        const getBody = await getResp.json();
        expect(getBody.count).toBe(0);
        expect(getBody.calls).toHaveLength(0);
    });

    test('POST /api/tools/call stores duration_ms and all fields correctly', async ({ request }) => {
        const ts = new Date().toISOString();
        const response = await request.post(`${BASE_URL}/api/tools/call`, {
            data: {
                tool_name: 'slack_send_message',
                input: { channel: '#general', message: 'hello' },
                result: 'Message sent',
                duration_ms: 123,
                status: 'success',
                timestamp: ts
            }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.entry.tool_name).toBe('slack_send_message');
        expect(body.entry.duration_ms).toBe(123);
        expect(body.entry.status).toBe('success');
        expect(body.entry.input).toMatchObject({ channel: '#general' });
    });

    test('POST /api/tools/call with error status records correctly', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/tools/call`, {
            data: {
                tool_name: 'linear_get_issue',
                input: { issue_key: 'AI-999' },
                result: 'Error: Issue not found',
                duration_ms: 15,
                status: 'error'
            }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.entry.status).toBe('error');
        expect(body.entry.duration_ms).toBe(15);
        expect(body.entry.tool_name).toBe('linear_get_issue');
    });

});

// ---------------------------------------------------------------------------
// UI Tests
// ---------------------------------------------------------------------------

test.describe('AI-78: Tool Call Transparency UI', () => {

    test('Tool call block shows duration in header after "linear status" message', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });

        // Send a message that triggers a Linear tool call
        await page.fill('#chat-input', 'linear status');
        await page.press('#chat-input', 'Enter');

        // Wait for tool call block to appear
        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Duration should be visible in header
        const durationEl = page.locator('[data-testid="tool-call-duration"]').first();
        await expect(durationEl).toBeVisible({ timeout: 5000 });
        const durationText = await durationEl.textContent();
        expect(durationText).toMatch(/\d+ms/);
    });

    test('Tool call block shows success checkmark for success status', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });

        await page.fill('#chat-input', 'linear status');
        await page.press('#chat-input', 'Enter');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Status element should be visible and show success (checkmark)
        const statusEl = page.locator('[data-testid="tool-call-status"]').first();
        await expect(statusEl).toBeVisible({ timeout: 5000 });
        const statusText = await statusEl.textContent();
        // Should not say "Failed"
        expect(statusText).not.toMatch(/failed/i);
        // Should have success class
        const statusClass = await statusEl.getAttribute('class');
        expect(statusClass).toContain('success');
    });

    test('Tool call block shows error status with error CSS class', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });

        // Send a message that triggers a simulated failure
        await page.fill('#chat-input', 'get AI-1 fail');
        await page.press('#chat-input', 'Enter');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Error block should have the 'error' class
        const errorBlock = page.locator('[data-testid="tool-call-block"].error').first();
        await expect(errorBlock).toBeVisible({ timeout: 5000 });

        // Status element should indicate error/failed
        const statusEl = page.locator('[data-testid="tool-call-status"].error').first();
        await expect(statusEl).toBeVisible({ timeout: 5000 });
        const statusText = await statusEl.textContent();
        expect(statusText).toMatch(/failed/i);
    });

    test('Tool call block body is collapsible - starts hidden, expands on click', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });

        await page.fill('#chat-input', 'linear status');
        await page.press('#chat-input', 'Enter');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Body should start hidden
        const body = page.locator('[data-testid="tool-call-body"]').first();
        await expect(body).toHaveClass(/hidden/, { timeout: 5000 });

        // Click header to expand
        const header = page.locator('[data-testid="tool-call-header"]').first();
        await header.click();

        // Body should no longer be hidden
        await expect(body).not.toHaveClass(/hidden/, { timeout: 3000 });
    });

    test('Tool call block body contains Input and Result sections', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });

        await page.fill('#chat-input', 'linear status');
        await page.press('#chat-input', 'Enter');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Expand the block
        const header = page.locator('[data-testid="tool-call-header"]').first();
        await header.click();

        // Body should contain Input and Result
        const body = page.locator('[data-testid="tool-call-body"]').first();
        const bodyText = await body.textContent();
        expect(bodyText).toMatch(/input/i);
        expect(bodyText).toMatch(/result/i);
    });

    test('data-status attribute reflects success for successful tool calls', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });

        await page.fill('#chat-input', 'list issues');
        await page.press('#chat-input', 'Enter');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        const block = page.locator('[data-testid="tool-call-block"]').first();
        const dataStatus = await block.getAttribute('data-status');
        expect(dataStatus).toBe('success');
    });

    test('Multiple tool calls from "list issues" and "linear status" both show in chat', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });

        // First tool call
        await page.fill('#chat-input', 'list issues');
        await page.press('#chat-input', 'Enter');
        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Second tool call
        await page.fill('#chat-input', 'linear status');
        await page.press('#chat-input', 'Enter');

        // Wait for at least 2 tool call blocks
        await page.waitForFunction(() => {
            return document.querySelectorAll('[data-testid="tool-call-block"]').length >= 2;
        }, { timeout: 10000 });

        const blocks = page.locator('[data-testid="tool-call-block"]');
        const count = await blocks.count();
        expect(count).toBeGreaterThanOrEqual(2);
    });

});
