/**
 * Playwright Tests - AI-130: Agent Controls (Pause, Resume & Requirement Editing)
 *
 * Tests:
 *   1. API: POST /api/agents/{agent_id}/pause
 *   2. API: POST /api/agents/{agent_id}/resume
 *   3. API: POST /api/agents/pause-all
 *   4. API: POST /api/agents/resume-all
 *   5. API: GET  /api/agents/{agent_id}/requirements
 *   6. API: PUT  /api/agents/{agent_id}/requirements
 *   7. API: GET  /api/agent-controls
 *   8. UI:  Pause All / Resume All buttons visible in toolbar
 *   9. UI:  Agent control cards render with Pause/Resume buttons
 *  10. UI:  Requirements editor modal opens and saves
 *  11. UI:  Paused count badge updates
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8420';
const TEST_AGENT_ID = 'coding_agent';

// ---------------------------------------------------------------------------
// API Tests
// ---------------------------------------------------------------------------

test.describe('AI-130: Agent Controls API', () => {

    test('POST /api/agents/{agent_id}/pause returns 200 and paused:true', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/agents/${TEST_AGENT_ID}/pause`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('agent_id', TEST_AGENT_ID);
        expect(body).toHaveProperty('paused', true);
        expect(body).toHaveProperty('timestamp');
    });

    test('GET /api/agents/{agent_id}/requirements returns current requirements', async ({ request }) => {
        // First set some requirements via pause (agent should be in paused state from previous test)
        const response = await request.get(`${BASE_URL}/api/agents/${TEST_AGENT_ID}/requirements`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('agent_id', TEST_AGENT_ID);
        expect(body).toHaveProperty('requirements');
        expect(body).toHaveProperty('paused');
        expect(body).toHaveProperty('timestamp');
    });

    test('PUT /api/agents/{agent_id}/requirements updates and returns requirements', async ({ request }) => {
        const newReqs = 'Implement feature AI-42: Build a robust user authentication system with MFA support.';
        const response = await request.put(
            `${BASE_URL}/api/agents/${TEST_AGENT_ID}/requirements`,
            {
                data: { requirements: newReqs },
                headers: { 'Content-Type': 'application/json' }
            }
        );
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('agent_id', TEST_AGENT_ID);
        expect(body).toHaveProperty('requirements', newReqs);
        expect(body).toHaveProperty('timestamp');
    });

    test('GET /api/agents/{agent_id}/requirements returns updated requirements after PUT', async ({ request }) => {
        const newReqs = 'Updated: Use secure token-based authentication with refresh tokens.';
        // Update first
        await request.put(
            `${BASE_URL}/api/agents/${TEST_AGENT_ID}/requirements`,
            { data: { requirements: newReqs }, headers: { 'Content-Type': 'application/json' } }
        );
        // Then read back
        const response = await request.get(`${BASE_URL}/api/agents/${TEST_AGENT_ID}/requirements`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.requirements).toBe(newReqs);
    });

    test('PUT /api/agents/{agent_id}/requirements returns 400 for missing requirements field', async ({ request }) => {
        const response = await request.put(
            `${BASE_URL}/api/agents/${TEST_AGENT_ID}/requirements`,
            { data: {}, headers: { 'Content-Type': 'application/json' } }
        );
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body).toHaveProperty('error');
    });

    test('POST /api/agents/{agent_id}/resume returns 200 and paused:false', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/agents/${TEST_AGENT_ID}/resume`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('agent_id', TEST_AGENT_ID);
        expect(body).toHaveProperty('paused', false);
        expect(body).toHaveProperty('timestamp');
    });

    test('POST /api/agents/pause-all returns 200 with agent_ids list', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/agents/pause-all`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('paused_count');
        expect(body).toHaveProperty('agent_ids');
        expect(Array.isArray(body.agent_ids)).toBe(true);
        expect(body).toHaveProperty('timestamp');
    });

    test('POST /api/agents/resume-all returns 200 with agent_ids list', async ({ request }) => {
        const response = await request.post(`${BASE_URL}/api/agents/resume-all`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status', 'ok');
        expect(body).toHaveProperty('resumed_count');
        expect(body).toHaveProperty('agent_ids');
        expect(Array.isArray(body.agent_ids)).toBe(true);
        expect(body).toHaveProperty('timestamp');
    });

    test('GET /api/agent-controls returns control state for all agents', async ({ request }) => {
        // Pause one agent first to ensure state exists
        await request.post(`${BASE_URL}/api/agents/${TEST_AGENT_ID}/pause`);

        const response = await request.get(`${BASE_URL}/api/agent-controls`);
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('agent_controls');
        expect(body).toHaveProperty('total_agents');
        expect(body).toHaveProperty('paused_count');
        expect(body).toHaveProperty('timestamp');
        // The paused agent should be in the controls
        expect(body.agent_controls).toHaveProperty(TEST_AGENT_ID);
        expect(body.agent_controls[TEST_AGENT_ID]).toHaveProperty('paused', true);
    });

    test('Pause/resume cycle: pause then resume correctly toggles state', async ({ request }) => {
        const agentId = 'testing_agent';

        // Pause
        const pauseResp = await request.post(`${BASE_URL}/api/agents/${agentId}/pause`);
        expect(pauseResp.status()).toBe(200);
        const pauseBody = await pauseResp.json();
        expect(pauseBody.paused).toBe(true);

        // Verify via requirements endpoint
        const getResp = await request.get(`${BASE_URL}/api/agents/${agentId}/requirements`);
        expect(getResp.status()).toBe(200);
        const getBody = await getResp.json();
        expect(getBody.paused).toBe(true);

        // Resume
        const resumeResp = await request.post(`${BASE_URL}/api/agents/${agentId}/resume`);
        expect(resumeResp.status()).toBe(200);
        const resumeBody = await resumeResp.json();
        expect(resumeBody.paused).toBe(false);
    });
});

// ---------------------------------------------------------------------------
// UI Tests
// ---------------------------------------------------------------------------

test.describe('AI-130: Agent Controls UI', () => {

    test.beforeEach(async ({ page }) => {
        // Navigate to dashboard and wait for it to load
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('Pause All and Resume All buttons are visible in toolbar', async ({ page }) => {
        // Wait for agent controls toolbar to be present
        await expect(page.locator('#agent-controls-toolbar')).toBeVisible();
        await expect(page.locator('#btn-pause-all')).toBeVisible();
        await expect(page.locator('#btn-resume-all')).toBeVisible();
    });

    test('Agent controls toolbar contains "Agent Controls" title', async ({ page }) => {
        const toolbar = page.locator('#agent-controls-toolbar');
        await expect(toolbar).toBeVisible();
        await expect(toolbar).toContainText('Agent Controls');
    });

    test('Agent controls section is visible on the page', async ({ page }) => {
        await expect(page.locator('#agent-controls-section')).toBeVisible();
    });

    test('Agent control cards render after page load', async ({ page }) => {
        // Wait for cards to populate (setTimeout of 1000ms in JS)
        await page.waitForTimeout(2500);
        const grid = page.locator('#agent-controls-grid');
        await expect(grid).toBeVisible();
        // Should have at least one card
        const cards = grid.locator('.agent-control-card');
        await expect(cards.first()).toBeVisible({ timeout: 5000 });
    });

    test('Agent control card has Pause button visible', async ({ page }) => {
        await page.waitForTimeout(2500);
        const grid = page.locator('#agent-controls-grid');
        // At least one pause button should exist
        const pauseBtn = grid.locator('.btn-pause').first();
        await expect(pauseBtn).toBeVisible({ timeout: 5000 });
    });

    test('Agent control card has Edit Requirements button', async ({ page }) => {
        await page.waitForTimeout(2500);
        const grid = page.locator('#agent-controls-grid');
        const editBtn = grid.locator('.btn-edit-req').first();
        await expect(editBtn).toBeVisible({ timeout: 5000 });
    });

    test('Clicking Pause button on an agent card changes it to Resume', async ({ page }) => {
        await page.waitForTimeout(2500);

        // Find first pause button and click it
        const firstPauseBtn = page.locator('#agent-controls-grid .btn-pause').first();
        await expect(firstPauseBtn).toBeVisible({ timeout: 5000 });
        await firstPauseBtn.click();

        // After pause, that card should now show a Resume button
        await page.waitForTimeout(500);
        const resumeBtn = page.locator('#agent-controls-grid .btn-resume').first();
        await expect(resumeBtn).toBeVisible({ timeout: 3000 });
    });

    test('Paused count badge appears after pausing an agent', async ({ page }) => {
        await page.waitForTimeout(2500);

        // Pause one agent via API to ensure badge shows
        await page.evaluate(async (baseUrl) => {
            await fetch(`${baseUrl}/api/agents/coding_agent/pause`, { method: 'POST' });
        }, BASE_URL);

        // Trigger UI refresh
        await page.evaluate(() => { if (typeof refreshAgentControls === 'function') refreshAgentControls(); });
        await page.waitForTimeout(1000);

        const badge = page.locator('#paused-count-badge');
        await expect(badge).toBeVisible({ timeout: 3000 });
        await expect(badge).toContainText('paused');
    });

    test('Requirements modal opens when Edit Requirements is clicked', async ({ page }) => {
        await page.waitForTimeout(2500);

        // Click first edit requirements button
        const editBtn = page.locator('#agent-controls-grid .btn-edit-req').first();
        await expect(editBtn).toBeVisible({ timeout: 5000 });
        await editBtn.click();

        // Modal should be visible
        const modal = page.locator('#requirements-modal');
        await expect(modal).toBeVisible({ timeout: 3000 });
        await expect(modal.locator('#requirements-textarea')).toBeVisible();
    });

    test('Requirements modal closes when Cancel is clicked', async ({ page }) => {
        await page.waitForTimeout(2500);

        // Open modal
        const editBtn = page.locator('#agent-controls-grid .btn-edit-req').first();
        await expect(editBtn).toBeVisible({ timeout: 5000 });
        await editBtn.click();

        const modal = page.locator('#requirements-modal');
        await expect(modal).toBeVisible({ timeout: 3000 });

        // Click cancel
        await modal.locator('button:has-text("Cancel")').click();
        await expect(modal).not.toBeVisible({ timeout: 2000 });
    });

    test('Requirements modal shows agent ID label', async ({ page }) => {
        await page.waitForTimeout(2500);

        const editBtn = page.locator('#agent-controls-grid .btn-edit-req').first();
        await expect(editBtn).toBeVisible({ timeout: 5000 });
        await editBtn.click();

        const modal = page.locator('#requirements-modal');
        await expect(modal).toBeVisible({ timeout: 3000 });
        // Agent ID label should be non-empty
        const agentLabel = modal.locator('#modal-agent-id-label');
        await expect(agentLabel).toBeVisible();
        const labelText = await agentLabel.textContent();
        expect(labelText.trim().length).toBeGreaterThan(0);
    });

    test('Requirements modal can type and save requirements', async ({ page }) => {
        await page.waitForTimeout(2500);

        const editBtn = page.locator('#agent-controls-grid .btn-edit-req').first();
        await expect(editBtn).toBeVisible({ timeout: 5000 });
        await editBtn.click();

        const modal = page.locator('#requirements-modal');
        await expect(modal).toBeVisible({ timeout: 3000 });

        // Type requirement text
        const textarea = modal.locator('#requirements-textarea');
        await textarea.fill('Implement AI-42: User authentication with MFA and OAuth2 support.');

        // Click Save
        await modal.locator('button:has-text("Save Requirements")').click();

        // Success message should appear
        const successMsg = modal.locator('#modal-success-msg');
        await expect(successMsg).toBeVisible({ timeout: 3000 });
    });

    test('Clicking Pause All button calls pause-all API and updates UI', async ({ page }) => {
        await page.waitForTimeout(2500);

        // Intercept the API call
        let pauseAllCalled = false;
        await page.route('**/api/agents/pause-all', route => {
            pauseAllCalled = true;
            route.continue();
        });

        const pauseAllBtn = page.locator('#btn-pause-all');
        await expect(pauseAllBtn).toBeVisible();
        await pauseAllBtn.click();

        await page.waitForTimeout(1000);
        expect(pauseAllCalled).toBe(true);
    });

    test('Clicking Resume All button calls resume-all API', async ({ page }) => {
        await page.waitForTimeout(2500);

        let resumeAllCalled = false;
        await page.route('**/api/agents/resume-all', route => {
            resumeAllCalled = true;
            route.continue();
        });

        const resumeAllBtn = page.locator('#btn-resume-all');
        await expect(resumeAllBtn).toBeVisible();
        await resumeAllBtn.click();

        await page.waitForTimeout(1000);
        expect(resumeAllCalled).toBe(true);
    });

    test('Requirements modal closes when clicking outside', async ({ page }) => {
        await page.waitForTimeout(2500);

        const editBtn = page.locator('#agent-controls-grid .btn-edit-req').first();
        await expect(editBtn).toBeVisible({ timeout: 5000 });
        await editBtn.click();

        const modal = page.locator('#requirements-modal');
        await expect(modal).toBeVisible({ timeout: 3000 });

        // Click on the overlay (outside the modal box)
        await page.mouse.click(10, 10);
        await expect(modal).not.toBeVisible({ timeout: 2000 });
    });
});
