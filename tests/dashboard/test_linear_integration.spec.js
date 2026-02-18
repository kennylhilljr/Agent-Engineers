/**
 * Playwright Tests - AI-75: Linear Integration - Issue Queries and Management
 *
 * Tests:
 *   1. API: GET /api/integrations/linear/status returns connected status
 *   2. API: GET /api/integrations/linear/issue/{key} returns issue data for known key
 *   3. API: GET /api/integrations/linear/issue/{key} returns placeholder for unknown key
 *   4. API: GET /api/integrations/linear/issues returns list of 5 issues
 *   5. API: GET /api/integrations/linear/issues?status=Done filters by status
 *   6. API: POST /api/integrations/linear/query action=get_issue returns summary
 *   7. API: POST /api/integrations/linear/query action=list_issues returns issues
 *   8. API: POST /api/integrations/linear/query action=create_issue creates issue
 *   9. API: POST /api/integrations/linear/query action=transition_issue transitions status
 *  10. API: POST /api/integrations/linear/query action=get_board returns board columns
 *  11. UI:  Tool call block renders in chat when "status of AI-42?" is sent
 *  12. UI:  Tool call block has correct data-testid attributes
 *  13. UI:  Issue key pattern detection triggers tool call (AI-1)
 *  14. UI:  "list issues" message triggers list tool call
 *  15. UI:  "linear status" message triggers status tool call
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8420';

// ---------------------------------------------------------------------------
// API Tests
// ---------------------------------------------------------------------------

test.describe('AI-75: Linear Integration API', () => {

    test('GET /api/integrations/linear/status returns connected:true and tool_count:39', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/linear/status`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('connected', true);
        expect(body).toHaveProperty('tool_count', 39);
        expect(body).toHaveProperty('service', 'Linear');
        expect(body).toHaveProperty('timestamp');
    });

    test('GET /api/integrations/linear/issue/AI-1 returns issue data with expected fields', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/linear/issue/AI-1`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('issue');
        const issue = body.issue;
        expect(issue).toHaveProperty('id');
        expect(issue).toHaveProperty('key', 'AI-1');
        expect(issue).toHaveProperty('title');
        expect(issue).toHaveProperty('status');
        expect(issue).toHaveProperty('assignee');
        expect(issue).toHaveProperty('priority');
        expect(issue).toHaveProperty('description');
    });

    test('GET /api/integrations/linear/issue/AI-42 returns In Progress status', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/linear/issue/AI-42`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.issue).toHaveProperty('key', 'AI-42');
        expect(body.issue).toHaveProperty('status', 'In Progress');
        expect(body.issue).toHaveProperty('assignee', 'Kenny H');
    });

    test('GET /api/integrations/linear/issue/AI-999 returns placeholder for unknown key', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/linear/issue/AI-999`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('issue');
        expect(body.issue).toHaveProperty('key', 'AI-999');
        // Should have all required fields even for unknown keys
        expect(body.issue).toHaveProperty('title');
        expect(body.issue).toHaveProperty('status');
        expect(body.issue).toHaveProperty('assignee');
    });

    test('GET /api/integrations/linear/issues returns list of 5 issues', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/linear/issues`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('issues');
        expect(body).toHaveProperty('count');
        expect(Array.isArray(body.issues)).toBe(true);
        expect(body.issues.length).toBe(5);
        expect(body.count).toBe(5);
        // Each issue should have required fields
        for (const issue of body.issues) {
            expect(issue).toHaveProperty('key');
            expect(issue).toHaveProperty('title');
            expect(issue).toHaveProperty('status');
        }
    });

    test('GET /api/integrations/linear/issues?status=Done filters to only Done issues', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/integrations/linear/issues?status=Done`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('issues');
        expect(Array.isArray(body.issues)).toBe(true);
        // All returned issues should have status "Done"
        for (const issue of body.issues) {
            expect(issue.status).toBe('Done');
        }
    });

    test('POST /api/integrations/linear/query action=get_issue returns issue summary', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/linear/query`, {
            data: { action: 'get_issue', params: { issue_key: 'AI-42' } },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('action', 'get_issue');
        expect(body).toHaveProperty('result');
        expect(body).toHaveProperty('summary');
        expect(body.summary).toContain('AI-42');
        expect(body.summary).toContain('In Progress');
    });

    test('POST /api/integrations/linear/query action=list_issues returns issues array', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/linear/query`, {
            data: { action: 'list_issues', params: {} },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('action', 'list_issues');
        expect(body).toHaveProperty('result');
        expect(Array.isArray(body.result)).toBe(true);
        expect(body.result.length).toBeGreaterThan(0);
    });

    test('POST /api/integrations/linear/query action=create_issue creates a new issue', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/linear/query`, {
            data: {
                action: 'create_issue',
                params: {
                    title: 'Bug: Login page crashes on submit',
                    description: 'The login form causes a 500 error when submitted with valid credentials.',
                    priority: 'High'
                }
            },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('action', 'create_issue');
        expect(body).toHaveProperty('result');
        expect(body.result).toHaveProperty('title', 'Bug: Login page crashes on submit');
        expect(body.result).toHaveProperty('priority', 'High');
        expect(body).toHaveProperty('summary');
        expect(body.summary).toContain('Bug: Login page crashes on submit');
    });

    test('POST /api/integrations/linear/query action=transition_issue changes status', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/linear/query`, {
            data: {
                action: 'transition_issue',
                params: { issue_key: 'AI-42', status: 'Done' }
            },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('action', 'transition_issue');
        expect(body).toHaveProperty('result');
        expect(body.result).toHaveProperty('status', 'Done');
        expect(body).toHaveProperty('summary');
        expect(body.summary).toContain('Done');
    });

    test('POST /api/integrations/linear/query action=get_board returns board columns', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/linear/query`, {
            data: { action: 'get_board', params: {} },
            headers: { 'Content-Type': 'application/json' }
        });
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('action', 'get_board');
        expect(body).toHaveProperty('result');
        expect(body.result).toHaveProperty('backlog');
        expect(body.result).toHaveProperty('in_progress');
        expect(body.result).toHaveProperty('done');
        expect(body).toHaveProperty('summary');
    });

    test('POST /api/integrations/linear/query with unknown action returns 400', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/integrations/linear/query`, {
            data: { action: 'unknown_action', params: {} },
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

test.describe('AI-75: Linear Integration UI - Tool Call Blocks', () => {

    test('Typing "What is the status of AI-42?" renders a tool call block in chat', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });

        // Wait for initial load
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'What is the status of AI-42?');
        await page.click('#chat-send-btn');

        // Wait for tool call block to appear (API call takes time)
        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });
        const block = page.locator('[data-testid="tool-call-block"]');
        await expect(block).toBeVisible();
    });

    test('Tool call block has correct data-testid attributes', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'What is the status of AI-1?');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Verify structural testids
        await expect(page.locator('[data-testid="tool-call-header"]')).toBeVisible();
        await expect(page.locator('[data-testid="tool-call-name"]')).toBeVisible();
        await expect(page.locator('[data-testid="tool-call-toggle"]')).toBeVisible();

        // Verify the tool name shows get_issue
        const toolName = page.locator('[data-testid="tool-call-name"]');
        await expect(toolName).toContainText('get_issue');
    });

    test('Tool call block is collapsible - body starts hidden and toggles open', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'Status of AI-68');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Body should start hidden
        const body = page.locator('[data-testid="tool-call-body"]').first();
        await expect(body).toHaveClass(/hidden/);

        // Click header to expand
        await page.locator('[data-testid="tool-call-header"]').first().click();
        await expect(body).not.toHaveClass(/hidden/);
    });

    test('"list issues" message triggers list_issues tool call block', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'Please list issues');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });
        const toolName = page.locator('[data-testid="tool-call-name"]').first();
        await expect(toolName).toContainText('list_issues');
    });

    test('"linear status" message triggers linear_status tool call block', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'linear status');
        await page.click('#chat-send-btn');

        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });
        const toolName = page.locator('[data-testid="tool-call-name"]').first();
        await expect(toolName).toContainText('linear_status');
    });

    test('After tool call, an AI message with issue details also appears', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        await page.fill('#chat-input', 'What is the status of AI-75?');
        await page.click('#chat-send-btn');

        // Wait for both tool call block and AI response message
        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });
        const aiMessages = page.locator('[data-testid="chat-message-ai"]');
        await expect(aiMessages.last()).toBeVisible();
    });

    test('Screenshot: save tool call block visual to screenshots/ai-75-linear-integration.png', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForSelector('#chat-input', { timeout: 10000 });
        await page.waitForTimeout(1000);

        // Send a message that triggers a tool call
        await page.fill('#chat-input', 'What is the status of AI-42?');
        await page.click('#chat-send-btn');

        // Wait for tool call block to render
        await page.waitForSelector('[data-testid="tool-call-block"]', { timeout: 8000 });

        // Click to expand the tool call body
        await page.locator('[data-testid="tool-call-header"]').first().click();
        await page.waitForTimeout(500);

        // Take full-page screenshot
        await page.screenshot({
            path: 'screenshots/ai-75-linear-integration.png',
            fullPage: false
        });
    });

});
