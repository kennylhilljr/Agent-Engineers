/**
 * AI-262: Test Conversation Window Issues
 * Tests to verify current chat functionality and issues
 */

const { test, expect } = require('@playwright/test');

test.describe('AI-262: Conversation Window Issues', () => {
    const chatUrl = 'http://localhost:8080/dashboard/test_chat.html';

    test.beforeEach(async ({ page }) => {
        await page.goto(chatUrl);
        await page.waitForLoadState('networkidle');
    });

    test('ISSUE 1: Check scroll behavior and input position', async ({ page }) => {
        const chatMessages = page.locator('#chat-messages');
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Take initial screenshot
        await page.screenshot({
            path: 'screenshots/ai262-01-initial-state.png',
            fullPage: true
        });

        // Send several messages to trigger scrolling
        const messages = [
            'First test message',
            'Second test message',
            'Third test message',
            'Fourth test message',
            'Fifth test message'
        ];

        for (const msg of messages) {
            await chatInput.fill(msg);
            await sendButton.click();
            await page.waitForTimeout(1000);
        }

        // Take screenshot after messages
        await page.screenshot({
            path: 'screenshots/ai262-02-after-messages.png',
            fullPage: true
        });

        // Check scroll position
        const scrollTop = await chatMessages.evaluate(el => el.scrollTop);
        const scrollHeight = await chatMessages.evaluate(el => el.scrollHeight);
        const clientHeight = await chatMessages.evaluate(el => el.clientHeight);

        console.log(`Scroll info: top=${scrollTop}, height=${scrollHeight}, client=${clientHeight}`);

        // The chat should auto-scroll to bottom (scrollTop + clientHeight should be close to scrollHeight)
        const scrolledToBottom = (scrollTop + clientHeight) >= (scrollHeight - 50);
        console.log(`Scrolled to bottom: ${scrolledToBottom}`);

        // Count messages
        const userMessages = await page.locator('[data-testid="chat-message-user"]').count();
        const aiMessages = await page.locator('[data-testid="chat-message-ai"]').count();

        console.log(`User messages: ${userMessages}, AI messages: ${aiMessages}`);
    });

    test('ISSUE 2: Check if AI responses are actually returned', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Send a test message
        await chatInput.fill('Hello, can you hear me?');
        await sendButton.click();

        // Wait for user message to appear
        await page.waitForTimeout(500);

        const userMessage = page.locator('[data-testid="chat-message-user"]').first();
        await expect(userMessage).toBeVisible();

        // Take screenshot showing only user message
        await page.screenshot({
            path: 'screenshots/ai262-03-user-message-only.png',
            fullPage: true
        });

        // Wait longer for AI response
        await page.waitForTimeout(3000);

        // Take screenshot to see if AI responded
        await page.screenshot({
            path: 'screenshots/ai262-04-waiting-for-ai.png',
            fullPage: true
        });

        // Check if AI message appeared
        const aiMessages = await page.locator('[data-testid="chat-message-ai"]').count();
        console.log(`AI messages count: ${aiMessages}`);

        if (aiMessages > 0) {
            const aiMessage = page.locator('[data-testid="chat-message-ai"]').first();
            const aiText = await aiMessage.textContent();
            console.log(`AI response: ${aiText}`);
        } else {
            console.log('NO AI RESPONSE DETECTED - This is the bug!');
        }
    });

    test('ISSUE 3: Check chat API endpoint directly', async ({ request }) => {
        // Test the chat API endpoint
        const response = await request.post('http://localhost:8080/api/chat', {
            data: {
                message: 'Test message',
                provider: 'claude',
                model: 'haiku-4.5'
            }
        });

        console.log(`API Status: ${response.status()}`);

        if (response.ok()) {
            const data = await response.json();
            console.log('API Response:', JSON.stringify(data, null, 2));
        } else {
            const text = await response.text();
            console.log('API Error:', text);
        }
    });

    test('ISSUE 4: Check if streaming endpoint works', async ({ page }) => {
        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        // Monitor network requests
        const requests = [];
        page.on('request', req => {
            if (req.url().includes('/api/chat')) {
                requests.push({
                    url: req.url(),
                    method: req.method(),
                    postData: req.postData()
                });
            }
        });

        const responses = [];
        page.on('response', async resp => {
            if (resp.url().includes('/api/chat')) {
                const status = resp.status();
                let body = null;
                try {
                    body = await resp.text();
                } catch (e) {
                    body = 'Could not read body';
                }
                responses.push({
                    url: resp.url(),
                    status,
                    body
                });
            }
        });

        // Send message
        await chatInput.fill('Test streaming response');
        await sendButton.click();

        await page.waitForTimeout(3000);

        console.log('Requests:', JSON.stringify(requests, null, 2));
        console.log('Responses:', JSON.stringify(responses, null, 2));
    });

    test('ISSUE 5: Check console errors', async ({ page }) => {
        const consoleMessages = [];
        page.on('console', msg => {
            consoleMessages.push({
                type: msg.type(),
                text: msg.text()
            });
        });

        const chatInput = page.locator('#chat-input');
        const sendButton = page.locator('#chat-send-btn');

        await chatInput.fill('Test for console errors');
        await sendButton.click();

        await page.waitForTimeout(2000);

        console.log('Console messages:', JSON.stringify(consoleMessages, null, 2));

        const errors = consoleMessages.filter(m => m.type === 'error');
        if (errors.length > 0) {
            console.log('ERRORS DETECTED:', errors);
        }
    });
});
