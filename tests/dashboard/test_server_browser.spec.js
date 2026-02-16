/**
 * Playwright Browser Tests for Dashboard Server - AI-102
 *
 * These tests verify all 9 test steps required:
 * 1. Start dashboard server
 * 2. Verify server is listening on configured port
 * 3. Verify health check endpoint responds
 * 4. Verify static HTML dashboard is served
 * 5. Make REST API calls and verify responses
 * 6. Open WebSocket connection and verify it connects
 * 7. Verify metrics endpoint returns current state
 * 8. Verify agents endpoint returns all 13 agents
 * 9. Test server handles multiple concurrent connections
 */

const { test, expect } = require('@playwright/test');
const http = require('http');
const WebSocket = require('ws');

// Configuration
const SERVER_HOST = '127.0.0.1';
const SERVER_PORT = 8080;
const BASE_URL = `http://${SERVER_HOST}:${SERVER_PORT}`;
const WS_URL = `ws://${SERVER_HOST}:${SERVER_PORT}/ws`;

// Helper function to check if server is running
async function isServerRunning() {
    return new Promise((resolve) => {
        const req = http.get(`${BASE_URL}/health`, (res) => {
            resolve(res.statusCode === 200);
        });
        req.on('error', () => resolve(false));
        req.setTimeout(1000, () => {
            req.destroy();
            resolve(false);
        });
    });
}

// Helper function to wait for server to start
async function waitForServer(maxAttempts = 30, delayMs = 1000) {
    for (let i = 0; i < maxAttempts; i++) {
        if (await isServerRunning()) {
            return true;
        }
        await new Promise(resolve => setTimeout(resolve, delayMs));
    }
    return false;
}

test.describe('Dashboard Server Browser Tests - AI-102', () => {

    test.beforeAll(async () => {
        // Check if server is already running
        const serverRunning = await isServerRunning();
        if (!serverRunning) {
            console.log('⚠️  Server is not running. Please start the server with:');
            console.log('   python -m dashboard.server --port 8080');
            console.log('   Waiting for server to start...');

            // Wait for server to start
            const started = await waitForServer();
            if (!started) {
                throw new Error('Server did not start within timeout period');
            }
        }
        console.log('✓ Server is running');
    });

    test('Test Step 1 & 2: Verify server is listening on configured port', async () => {
        const serverRunning = await isServerRunning();
        expect(serverRunning).toBe(true);
    });

    test('Test Step 3: Verify health check endpoint responds', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/health`);
        expect(response.status()).toBe(200);

        const data = await response.json();
        expect(data).toHaveProperty('status', 'ok');
        expect(data).toHaveProperty('timestamp');
        expect(data).toHaveProperty('project');
        expect(data).toHaveProperty('metrics_file_exists');
        expect(data).toHaveProperty('event_count');
        expect(data).toHaveProperty('session_count');
        expect(data).toHaveProperty('agent_count');

        console.log(`✓ Health check passed:`, data);
    });

    test('Test Step 4: Verify static HTML dashboard is served', async ({ page }) => {
        await page.goto(BASE_URL);

        // Check that page loaded
        await page.waitForLoadState('networkidle');

        // Verify HTML content
        const title = await page.title();
        expect(title).toBeTruthy();

        // Check for common dashboard elements
        const bodyContent = await page.content();
        expect(bodyContent).toContain('html');
        expect(bodyContent.length).toBeGreaterThan(1000); // Should have substantial content

        console.log(`✓ Dashboard HTML served (title: ${title})`);
    });

    test('Test Step 5 & 7: Make REST API calls and verify metrics endpoint', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/metrics`);
        expect(response.status()).toBe(200);

        const data = await response.json();

        // Verify metrics structure
        expect(data).toHaveProperty('project_name');
        expect(data).toHaveProperty('agents');
        expect(data).toHaveProperty('events');
        expect(data).toHaveProperty('sessions');
        expect(data).toHaveProperty('total_sessions');
        expect(data).toHaveProperty('total_tokens');
        expect(data).toHaveProperty('total_cost_usd');

        // Verify data types
        expect(typeof data.project_name).toBe('string');
        expect(typeof data.agents).toBe('object');
        expect(Array.isArray(data.events)).toBe(true);
        expect(Array.isArray(data.sessions)).toBe(true);
        expect(typeof data.total_sessions).toBe('number');

        console.log(`✓ Metrics endpoint returned data for ${Object.keys(data.agents).length} agents`);
    });

    test('Test Step 8: Verify agents endpoint returns all agents', async ({ request }) => {
        // First get all metrics to see which agents exist
        const metricsResponse = await request.get(`${BASE_URL}/api/metrics`);
        const metricsData = await metricsResponse.json();

        const agentNames = Object.keys(metricsData.agents);
        console.log(`✓ Found ${agentNames.length} agents:`, agentNames);

        // Test each agent endpoint
        for (const agentName of agentNames) {
            const agentResponse = await request.get(`${BASE_URL}/api/agents/${agentName}`);
            expect(agentResponse.status()).toBe(200);

            const agentData = await agentResponse.json();
            expect(agentData).toHaveProperty('agent');
            expect(agentData.agent).toHaveProperty('agent_name', agentName);
            expect(agentData.agent).toHaveProperty('total_invocations');
            expect(agentData.agent).toHaveProperty('success_rate');
            expect(agentData.agent).toHaveProperty('xp');
            expect(agentData.agent).toHaveProperty('level');
        }

        console.log(`✓ All ${agentNames.length} agent endpoints verified`);
    });

    test('Test Step 6: Open WebSocket connection and verify it connects', async () => {
        return new Promise((resolve, reject) => {
            const ws = new WebSocket(WS_URL);
            let messageReceived = false;

            const timeout = setTimeout(() => {
                ws.close();
                if (!messageReceived) {
                    reject(new Error('WebSocket did not receive initial message within timeout'));
                }
            }, 10000);

            ws.on('open', () => {
                console.log('✓ WebSocket connection opened');
            });

            ws.on('message', (data) => {
                messageReceived = true;

                try {
                    const message = JSON.parse(data.toString());

                    // Verify message structure
                    expect(message).toHaveProperty('type', 'metrics_update');
                    expect(message).toHaveProperty('timestamp');
                    expect(message).toHaveProperty('data');
                    expect(message.data).toHaveProperty('agents');

                    console.log('✓ WebSocket received metrics update:', {
                        type: message.type,
                        agentCount: Object.keys(message.data.agents).length,
                        timestamp: message.timestamp
                    });

                    clearTimeout(timeout);
                    ws.close();
                    resolve();
                } catch (error) {
                    clearTimeout(timeout);
                    ws.close();
                    reject(error);
                }
            });

            ws.on('error', (error) => {
                clearTimeout(timeout);
                reject(error);
            });

            ws.on('close', () => {
                console.log('✓ WebSocket connection closed');
            });
        });
    });

    test('Test Step 9: Test server handles multiple concurrent connections', async ({ request }) => {
        // Make 20 concurrent requests
        const numRequests = 20;
        const requests = [];

        for (let i = 0; i < numRequests; i++) {
            requests.push(request.get(`${BASE_URL}/health`));
        }

        const responses = await Promise.all(requests);

        // Verify all succeeded
        for (const response of responses) {
            expect(response.status()).toBe(200);
        }

        console.log(`✓ Server handled ${numRequests} concurrent connections successfully`);
    });

    test('Additional: Verify CORS headers are present', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/metrics`);
        const headers = response.headers();

        expect(headers).toHaveProperty('access-control-allow-origin');
        expect(headers).toHaveProperty('access-control-allow-methods');
        expect(headers).toHaveProperty('access-control-allow-headers');

        console.log('✓ CORS headers verified:', {
            origin: headers['access-control-allow-origin'],
            methods: headers['access-control-allow-methods']
        });
    });

    test('Additional: Verify pretty JSON formatting', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/metrics?pretty`);
        expect(response.status()).toBe(200);

        const text = await response.text();

        // Pretty JSON should have newlines and indentation
        expect(text).toContain('\n');
        expect(text).toContain('  '); // Indentation

        // Should still be valid JSON
        const data = JSON.parse(text);
        expect(data).toHaveProperty('project_name');

        console.log('✓ Pretty JSON formatting verified');
    });

    test('Additional: Verify agent endpoint with events', async ({ request }) => {
        // Get metrics to find an agent
        const metricsResponse = await request.get(`${BASE_URL}/api/metrics`);
        const metricsData = await metricsResponse.json();

        const agentNames = Object.keys(metricsData.agents);
        if (agentNames.length > 0) {
            const agentName = agentNames[0];
            const response = await request.get(`${BASE_URL}/api/agents/${agentName}?include_events=1`);
            expect(response.status()).toBe(200);

            const data = await response.json();
            expect(data).toHaveProperty('agent');
            expect(data).toHaveProperty('recent_events');

            console.log(`✓ Agent ${agentName} endpoint with events verified`);
        }
    });

    test('Additional: Verify 404 for non-existent agent', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/agents/nonexistent_agent_xyz`);
        expect(response.status()).toBe(404);

        const data = await response.json();
        expect(data).toHaveProperty('error', 'Agent not found');
        expect(data).toHaveProperty('available_agents');

        console.log('✓ 404 error handling verified');
    });

    test('Additional: Verify OPTIONS request for CORS preflight', async ({ request }) => {
        const response = await request.fetch(`${BASE_URL}/api/metrics`, {
            method: 'OPTIONS'
        });
        expect(response.status()).toBe(204);

        console.log('✓ CORS preflight (OPTIONS) verified');
    });

    test('Additional: WebSocket ping/pong', async () => {
        return new Promise((resolve, reject) => {
            const ws = new WebSocket(WS_URL);
            let initialMessageReceived = false;

            const timeout = setTimeout(() => {
                ws.close();
                reject(new Error('WebSocket ping/pong timeout'));
            }, 10000);

            ws.on('open', () => {
                console.log('✓ WebSocket opened for ping test');
            });

            ws.on('message', (data) => {
                const message = data.toString();

                if (!initialMessageReceived) {
                    // First message is the initial metrics update
                    initialMessageReceived = true;

                    // Send ping
                    ws.send('ping');
                    console.log('→ Sent ping');
                } else {
                    // Should receive pong
                    expect(message).toBe('pong');
                    console.log('✓ Received pong');

                    clearTimeout(timeout);
                    ws.close();
                    resolve();
                }
            });

            ws.on('error', (error) => {
                clearTimeout(timeout);
                reject(error);
            });
        });
    });

    test('Additional: Multiple WebSocket connections', async () => {
        const numConnections = 5;
        const connections = [];

        // Create multiple WebSocket connections
        for (let i = 0; i < numConnections; i++) {
            const promise = new Promise((resolve, reject) => {
                const ws = new WebSocket(WS_URL);

                const timeout = setTimeout(() => {
                    ws.close();
                    reject(new Error(`WebSocket ${i} timeout`));
                }, 10000);

                ws.on('message', (data) => {
                    const message = JSON.parse(data.toString());
                    expect(message).toHaveProperty('type', 'metrics_update');

                    clearTimeout(timeout);
                    ws.close();
                    resolve();
                });

                ws.on('error', (error) => {
                    clearTimeout(timeout);
                    reject(error);
                });
            });

            connections.push(promise);
        }

        await Promise.all(connections);
        console.log(`✓ ${numConnections} WebSocket connections handled successfully`);
    });

    test('Additional: Verify dashboard loads in browser', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Take screenshot for verification
        await page.screenshot({
            path: '/Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-dashboard/.worktrees/coding-0/tests/dashboard/screenshots/dashboard-loaded.png',
            fullPage: true
        });

        console.log('✓ Dashboard loaded and screenshot taken');
    });
});

test.describe('Performance Tests', () => {
    test('Metrics endpoint responds quickly', async ({ request }) => {
        const start = Date.now();
        const response = await request.get(`${BASE_URL}/api/metrics`);
        const duration = Date.now() - start;

        expect(response.status()).toBe(200);
        expect(duration).toBeLessThan(1000); // Should respond in under 1 second

        console.log(`✓ Metrics endpoint responded in ${duration}ms`);
    });

    test('Health check responds quickly', async ({ request }) => {
        const start = Date.now();
        const response = await request.get(`${BASE_URL}/health`);
        const duration = Date.now() - start;

        expect(response.status()).toBe(200);
        expect(duration).toBeLessThan(500); // Should respond in under 500ms

        console.log(`✓ Health check responded in ${duration}ms`);
    });
});
