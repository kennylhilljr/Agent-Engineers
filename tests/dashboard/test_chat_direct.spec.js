/**
 * AI-262: Direct Chat Test (using file:// protocol)
 * Tests chat functionality by loading HTML directly
 */

const { test, expect } = require('@playwright/test');
const path = require('path');

test.describe('AI-262: Direct Chat Test', () => {
    const chatFilePath = path.resolve(__dirname, '../../dashboard/test_chat.html');
    const chatFileUrl = `file://${chatFilePath}`;

    test('Load chat interface from file system', async ({ page }) => {
        // Navigate directly to the HTML file
        await page.goto(chatFileUrl);
        await page.waitForLoadState('domcontentloaded');

        // Take screenshot of initial state
        await page.screenshot({
            path: 'screenshots/ai262-direct-01-loaded.png',
            fullPage: true
        });

        // Check if basic elements are present
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');
        const chatMessages = page.locator('#chat-messages');

        await expect(chatInput).toBeVisible({ timeout: 5000 });
        await expect(sendButton).toBeVisible();
        await expect(chatMessages).toBeVisible();

        console.log('Chat interface loaded successfully');
    });

    test('Check scroll behavior', async ({ page }) => {
        await page.goto(chatFileUrl);
        await page.waitForLoadState('domcontentloaded');

        const chatMessages = page.locator('#chat-messages');
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Wait for interface to be ready
        await chatInput.waitFor({ state: 'visible', timeout: 5000 });

        // Get initial dimensions
        const initialHeight = await chatMessages.evaluate(el => ({
            scrollTop: el.scrollTop,
            scrollHeight: el.scrollHeight,
            clientHeight: el.clientHeight
        }));

        console.log('Initial scroll state:', initialHeight);

        // Send a message
        await chatInput.fill('Test message for scroll');
        await sendButton.click();

        // Wait for user message to appear
        await page.waitForTimeout(1000);

        // Take screenshot
        await page.screenshot({
            path: 'screenshots/ai262-direct-02-after-user-message.png',
            fullPage: true
        });

        // Check scroll position after message
        const afterUserMessage = await chatMessages.evaluate(el => ({
            scrollTop: el.scrollTop,
            scrollHeight: el.scrollHeight,
            clientHeight: el.clientHeight,
            isAtBottom: (el.scrollTop + el.clientHeight) >= (el.scrollHeight - 50)
        }));

        console.log('After user message:', afterUserMessage);
        console.log('Scrolled to bottom:', afterUserMessage.isAtBottom);

        // Wait for AI response
        await page.waitForTimeout(2000);

        // Take screenshot after waiting for AI
        await page.screenshot({
            path: 'screenshots/ai262-direct-03-after-wait.png',
            fullPage: true
        });

        // Check if AI response appeared
        const aiMessageCount = await page.locator('[data-testid="chat-message-ai"]').count();
        console.log('AI messages count:', aiMessageCount);

        if (aiMessageCount === 0) {
            console.log('BUG CONFIRMED: No AI response appeared');
        }

        // Check final scroll position
        const finalScroll = await chatMessages.evaluate(el => ({
            scrollTop: el.scrollTop,
            scrollHeight: el.scrollHeight,
            clientHeight: el.clientHeight,
            isAtBottom: (el.scrollTop + el.clientHeight) >= (el.scrollHeight - 50)
        }));

        console.log('Final scroll state:', finalScroll);
    });

    test('Monitor console and network for errors', async ({ page }) => {
        const consoleMessages = [];
        const networkErrors = [];
        const requests = [];

        page.on('console', msg => {
            consoleMessages.push({
                type: msg.type(),
                text: msg.text()
            });
        });

        page.on('requestfailed', req => {
            networkErrors.push({
                url: req.url(),
                method: req.method(),
                failure: req.failure()
            });
        });

        page.on('request', req => {
            if (req.url().includes('/api/')) {
                requests.push({
                    url: req.url(),
                    method: req.method()
                });
            }
        });

        await page.goto(chatFileUrl);
        await page.waitForLoadState('domcontentloaded');

        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        await chatInput.waitFor({ state: 'visible', timeout: 5000 });
        await chatInput.fill('Test for monitoring');
        await sendButton.click();

        await page.waitForTimeout(3000);

        console.log('=== Console Messages ===');
        consoleMessages.forEach(msg => {
            console.log(`[${msg.type}] ${msg.text}`);
        });

        console.log('\n=== API Requests ===');
        requests.forEach(req => {
            console.log(`${req.method} ${req.url}`);
        });

        console.log('\n=== Network Errors ===');
        if (networkErrors.length > 0) {
            networkErrors.forEach(err => {
                console.log(`FAILED: ${err.method} ${err.url}`);
                console.log(`  Reason: ${JSON.stringify(err.failure)}`);
            });
        } else {
            console.log('No network errors detected');
        }

        // Take final screenshot
        await page.screenshot({
            path: 'screenshots/ai262-direct-04-monitored.png',
            fullPage: true
        });
    });
});
