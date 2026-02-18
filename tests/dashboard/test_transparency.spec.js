/**
 * Playwright Tests - AI-131: Transparency Features - Reasoning, Decisions & Code Streaming
 *
 * Tests:
 *   API:
 *     1.  POST /api/transparency/reasoning - create a reasoning event
 *     2.  POST /api/transparency/reasoning - returns 400 for missing agent field
 *     3.  POST /api/transparency/reasoning - returns 400 for missing decision field
 *     4.  POST /api/transparency/reasoning - returns 400 for missing complexity field
 *     5.  POST /api/transparency/reasoning - returns 400 for missing reasoning field
 *     6.  GET  /api/transparency/history   - returns stored events
 *     7.  GET  /api/transparency/history   - returns empty after DELETE
 *     8.  DELETE /api/transparency/history - clears events
 *     9.  POST /api/transparency/code-stream - emit a code-stream chunk
 *     10. POST /api/transparency/code-stream - emit a done=true chunk
 *     11. POST /api/transparency/code-stream - returns 400 for missing required fields
 *     12. GET  /api/transparency/history   - accumulates multiple events
 *   UI:
 *     13. Dashboard shows decision history panel
 *     14. Reasoning block renders in chat on WebSocket message
 *     15. Complexity badge shows COMPLEX style
 *     16. Complexity badge shows SIMPLE style
 *     17. Reasoning body is collapsed by default
 *     18. Reasoning block can be expanded/collapsed via toggle click
 *     19. Decision history panel updates after reasoning event
 *     20. Decision history toggle shows/hides entries
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8442';

// ---------------------------------------------------------------------------
// Helper: clear transparency history before each test
// ---------------------------------------------------------------------------
async function clearHistory(request) {
    await request.delete(`${BASE_URL}/api/transparency/history`);
}

// ---------------------------------------------------------------------------
// API Tests
// ---------------------------------------------------------------------------

test.describe('AI-131: Transparency API', () => {

    test.beforeEach(async ({ request }) => {
        await clearHistory(request);
    });

    test('POST /api/transparency/reasoning creates a reasoning event', async ({ request }) => {
        const payload = {
            agent: 'orchestrator',
            decision: 'Route to coding (sonnet)',
            complexity: 'COMPLEX',
            reasoning: 'auth keyword found. Routing to coding (sonnet).',
            timestamp: new Date().toISOString()
        };
        const response = await request.post(`${BASE_URL}/api/transparency/reasoning`, {
            data: payload,
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('event');
        expect(body.event).toHaveProperty('agent', 'orchestrator');
        expect(body.event).toHaveProperty('decision', 'Route to coding (sonnet)');
        expect(body.event).toHaveProperty('complexity', 'COMPLEX');
        expect(body.event).toHaveProperty('reasoning');
        expect(body.event).toHaveProperty('timestamp');
    });

    test('POST /api/transparency/reasoning returns 400 for missing agent', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/transparency/reasoning`, {
            data: { decision: 'x', complexity: 'SIMPLE', reasoning: 'y' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

    test('POST /api/transparency/reasoning returns 400 for missing decision', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/transparency/reasoning`, {
            data: { agent: 'orch', complexity: 'SIMPLE', reasoning: 'y' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

    test('POST /api/transparency/reasoning returns 400 for missing complexity', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/transparency/reasoning`, {
            data: { agent: 'orch', decision: 'x', reasoning: 'y' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

    test('POST /api/transparency/reasoning returns 400 for missing reasoning', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/transparency/reasoning`, {
            data: { agent: 'orch', decision: 'x', complexity: 'SIMPLE' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

    test('GET /api/transparency/history returns stored events', async ({ request }) => {
        // First POST a reasoning event
        await request.post(`${BASE_URL}/api/transparency/reasoning`, {
            data: {
                agent: 'orchestrator',
                decision: 'Route to coding_fast',
                complexity: 'SIMPLE',
                reasoning: 'No complex keywords found.',
                timestamp: new Date().toISOString()
            },
            headers: { 'Content-Type': 'application/json' }
        });

        const response = await request.get(`${BASE_URL}/api/transparency/history`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('history');
        expect(Array.isArray(body.history)).toBe(true);
        expect(body.history.length).toBe(1);
        expect(body.history[0]).toHaveProperty('agent', 'orchestrator');
        expect(body.history[0]).toHaveProperty('complexity', 'SIMPLE');
        expect(body).toHaveProperty('count', 1);
        expect(body).toHaveProperty('timestamp');
    });

    test('GET /api/transparency/history returns empty after DELETE', async ({ request }) => {
        // POST first
        await request.post(`${BASE_URL}/api/transparency/reasoning`, {
            data: { agent: 'orch', decision: 'x', complexity: 'SIMPLE', reasoning: 'y' },
            headers: { 'Content-Type': 'application/json' }
        });
        // DELETE
        const delResponse = await request.delete(`${BASE_URL}/api/transparency/history`);
        expect(delResponse.status()).toBe(200);
        const delBody = await delResponse.json();
        expect(delBody).toHaveProperty('status', 'ok');
        expect(delBody.cleared).toBeGreaterThanOrEqual(1);

        // GET should be empty
        const getResponse = await request.get(`${BASE_URL}/api/transparency/history`);
        const getBody = await getResponse.json();
        expect(getBody.history.length).toBe(0);
        expect(getBody.count).toBe(0);
    });

    test('DELETE /api/transparency/history clears all events', async ({ request }) => {
        // Add 3 events
        for (let i = 0; i < 3; i++) {
            await request.post(`${BASE_URL}/api/transparency/reasoning`, {
                data: { agent: `agent_${i}`, decision: `Decision ${i}`, complexity: 'SIMPLE', reasoning: `reason ${i}` },
                headers: { 'Content-Type': 'application/json' }
            });
        }
        // Verify 3 stored
        let getBody = (await (await request.get(`${BASE_URL}/api/transparency/history`)).json());
        expect(getBody.count).toBe(3);

        // Delete
        await request.delete(`${BASE_URL}/api/transparency/history`);
        getBody = (await (await request.get(`${BASE_URL}/api/transparency/history`)).json());
        expect(getBody.count).toBe(0);
        expect(getBody.history.length).toBe(0);
    });

    test('POST /api/transparency/code-stream emits a chunk', async ({ request }) => {
        const payload = {
            agent_id: 'coding',
            chunk: 'def authenticate_user():',
            file_path: 'src/auth.py',
            done: false
        };
        const response = await request.post(`${BASE_URL}/api/transparency/code-stream`, {
            data: payload,
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
    });

    test('POST /api/transparency/code-stream with done=true', async ({ request }) => {
        const payload = {
            agent_id: 'coding',
            chunk: '    return user',
            file_path: 'src/auth.py',
            done: true
        };
        const response = await request.post(`${BASE_URL}/api/transparency/code-stream`, {
            data: payload,
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
    });

    test('POST /api/transparency/code-stream returns 400 for missing required fields', async ({ request }) => {
        // Missing chunk
        const response = await request.post(`${BASE_URL}/api/transparency/code-stream`, {
            data: { agent_id: 'coding', file_path: 'auth.py' },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

    test('GET /api/transparency/history accumulates multiple events', async ({ request }) => {
        const complexities = ['COMPLEX', 'SIMPLE', 'COMPLEX'];
        for (let i = 0; i < complexities.length; i++) {
            await request.post(`${BASE_URL}/api/transparency/reasoning`, {
                data: {
                    agent: 'orchestrator',
                    decision: `Route decision ${i}`,
                    complexity: complexities[i],
                    reasoning: `Reason for decision ${i}`
                },
                headers: { 'Content-Type': 'application/json' }
            });
        }
        const response = await request.get(`${BASE_URL}/api/transparency/history`);
        const body = await response.json();
        expect(body.count).toBe(3);
        expect(body.history.length).toBe(3);
        // All events have required fields
        for (const event of body.history) {
            expect(event).toHaveProperty('agent');
            expect(event).toHaveProperty('decision');
            expect(event).toHaveProperty('complexity');
            expect(event).toHaveProperty('reasoning');
            expect(event).toHaveProperty('timestamp');
        }
    });
});

// ---------------------------------------------------------------------------
// UI Tests
// ---------------------------------------------------------------------------

test.describe('AI-131: Transparency UI', () => {

    test.beforeEach(async ({ request }) => {
        await clearHistory(request);
    });

    test('Decision history panel is present in the dashboard', async ({ page }) => {
        await page.goto(BASE_URL);
        const panel = page.locator('[data-testid="decision-history-panel"]');
        await expect(panel).toBeVisible();
    });

    test('Reasoning block renders in chat after POST to /api/transparency/reasoning', async ({ page, request }) => {
        await page.goto(BASE_URL);

        // Post a reasoning event via API (which the WebSocket will broadcast)
        // Since tests may not have a live WS connection, we inject the reasoning
        // by calling the JS function directly
        await page.evaluate(() => {
            if (window.chatInterface) {
                window.chatInterface.addReasoningBlock({
                    agent: 'orchestrator',
                    decision: 'Route to coding (sonnet)',
                    complexity: 'COMPLEX',
                    reasoning: 'Complexity: COMPLEX — auth keyword found. Routing to coding (sonnet).',
                    timestamp: new Date().toISOString()
                });
            }
        });

        // Reasoning block should appear in chat
        const reasoningBlock = page.locator('[data-testid="reasoning-block"]').first();
        await expect(reasoningBlock).toBeVisible({ timeout: 5000 });
    });

    test('Complexity badge shows COMPLEX styling', async ({ page }) => {
        await page.goto(BASE_URL);

        await page.evaluate(() => {
            if (window.chatInterface) {
                window.chatInterface.addReasoningBlock({
                    agent: 'orchestrator',
                    decision: 'Route to coding',
                    complexity: 'COMPLEX',
                    reasoning: 'auth keyword detected',
                    timestamp: new Date().toISOString()
                });
            }
        });

        const badge = page.locator('[data-testid="complexity-badge"]').first();
        await expect(badge).toBeVisible({ timeout: 5000 });
        await expect(badge).toHaveText('COMPLEX');
        await expect(badge).toHaveClass(/complex/);
    });

    test('Complexity badge shows SIMPLE styling', async ({ page }) => {
        await page.goto(BASE_URL);

        await page.evaluate(() => {
            if (window.chatInterface) {
                window.chatInterface.addReasoningBlock({
                    agent: 'orchestrator',
                    decision: 'Route to coding_fast',
                    complexity: 'SIMPLE',
                    reasoning: 'No complex keywords found.',
                    timestamp: new Date().toISOString()
                });
            }
        });

        const badge = page.locator('[data-testid="complexity-badge"]').first();
        await expect(badge).toBeVisible({ timeout: 5000 });
        await expect(badge).toHaveText('SIMPLE');
        await expect(badge).toHaveClass(/simple/);
    });

    test('Reasoning body is collapsed by default', async ({ page }) => {
        await page.goto(BASE_URL);

        await page.evaluate(() => {
            if (window.chatInterface) {
                window.chatInterface.addReasoningBlock({
                    agent: 'orchestrator',
                    decision: 'Route to coding',
                    complexity: 'COMPLEX',
                    reasoning: 'auth keyword found',
                    timestamp: new Date().toISOString()
                });
            }
        });

        const body = page.locator('[data-testid="reasoning-body"]').first();
        await expect(body).toBeAttached({ timeout: 5000 });
        // Should have 'hidden' class (collapsed by default)
        await expect(body).toHaveClass(/hidden/);
    });

    test('Reasoning block toggle expands and collapses the body', async ({ page }) => {
        await page.goto(BASE_URL);

        await page.evaluate(() => {
            if (window.chatInterface) {
                window.chatInterface.addReasoningBlock({
                    agent: 'orchestrator',
                    decision: 'Route to coding',
                    complexity: 'COMPLEX',
                    reasoning: 'auth keyword found',
                    timestamp: new Date().toISOString()
                });
            }
        });

        const header = page.locator('[data-testid="reasoning-header"]').first();
        const body = page.locator('[data-testid="reasoning-body"]').first();

        // Initially collapsed
        await expect(body).toHaveClass(/hidden/);

        // Click to expand
        await header.click();
        await expect(body).not.toHaveClass(/hidden/);

        // Click again to collapse
        await header.click();
        await expect(body).toHaveClass(/hidden/);
    });

    test('Decision history panel updates when updateDecisionHistoryPanel is called', async ({ page }) => {
        await page.goto(BASE_URL);

        await page.evaluate(() => {
            if (typeof updateDecisionHistoryPanel === 'function') {
                updateDecisionHistoryPanel({
                    agent: 'orchestrator',
                    decision: 'Route to coding (sonnet)',
                    complexity: 'COMPLEX',
                    reasoning: 'auth keyword found',
                    timestamp: new Date().toISOString()
                });
            }
        });

        const countEl = page.locator('[data-testid="decision-history-count"]');
        await expect(countEl).toBeVisible({ timeout: 5000 });
        await expect(countEl).toHaveText('1 event');

        const entries = page.locator('[data-testid="decision-history-entry"]');
        await expect(entries).toHaveCount(1);
    });

    test('Decision history toggle hides and shows the list', async ({ page }) => {
        await page.goto(BASE_URL);

        // Add an entry first
        await page.evaluate(() => {
            if (typeof updateDecisionHistoryPanel === 'function') {
                updateDecisionHistoryPanel({
                    agent: 'orchestrator',
                    decision: 'x',
                    complexity: 'SIMPLE',
                    reasoning: 'y',
                    timestamp: new Date().toISOString()
                });
            }
        });

        const list = page.locator('[data-testid="decision-history-list"]');
        const toggle = page.locator('[data-testid="decision-history-toggle"]');

        // List should be visible initially
        await expect(list).not.toHaveClass(/hidden/);

        // Click toggle to hide
        await toggle.click();
        await expect(list).toHaveClass(/hidden/);

        // Click again to show
        await toggle.click();
        await expect(list).not.toHaveClass(/hidden/);
    });
});
