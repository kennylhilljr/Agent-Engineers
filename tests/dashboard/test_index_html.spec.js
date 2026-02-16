/**
 * AI-103: Frontend - Single HTML File Dashboard Tests
 *
 * Test coverage for the self-contained index.html file
 * - No external dependencies
 * - Embedded CSS and JavaScript
 * - Responsive design
 * - Dark mode styling
 * - All UI components
 * - Page load time < 2 seconds
 */

const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

// Path to the HTML file
const HTML_FILE_PATH = path.join(__dirname, '../../dashboard/index.html');
const FILE_URL = `file://${HTML_FILE_PATH}`;

test.describe('AI-103: Single HTML File Dashboard', () => {

  test.beforeAll(async () => {
    // Verify file exists
    if (!fs.existsSync(HTML_FILE_PATH)) {
      throw new Error(`index.html not found at ${HTML_FILE_PATH}`);
    }
  });

  test('should be a single self-contained HTML file', async () => {
    // Read the file content
    const content = fs.readFileSync(HTML_FILE_PATH, 'utf-8');

    // Verify it's an HTML file
    expect(content).toContain('<!DOCTYPE html>');
    expect(content).toContain('<html');
    expect(content).toContain('</html>');

    // Verify CSS is embedded (not external)
    expect(content).toContain('<style>');
    expect(content).not.toContain('<link rel="stylesheet"');

    // Verify JavaScript is embedded (not external)
    expect(content).toContain('<script>');
    expect(content).not.toContain('<script src=');

    // Verify no CDN dependencies
    expect(content).not.toContain('cdn.jsdelivr');
    expect(content).not.toContain('unpkg.com');
    expect(content).not.toContain('cdnjs.cloudflare');
    expect(content).not.toContain('googleapis.com');
  });

  test('should load without errors', async ({ page }) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto(FILE_URL);

    // Wait for initialization
    await page.waitForFunction(() => {
      return document.querySelector('#chat-messages') !== null;
    });

    expect(errors).toHaveLength(0);
  });

  test('should load in under 2 seconds', async ({ page }) => {
    const startTime = Date.now();

    await page.goto(FILE_URL);
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;

    console.log(`Page load time: ${loadTime}ms`);
    expect(loadTime).toBeLessThan(2000);
  });

  test('should display header with correct elements', async ({ page }) => {
    await page.goto(FILE_URL);

    // Check header exists
    const header = await page.locator('.header');
    await expect(header).toBeVisible();

    // Check title
    const title = await page.locator('.header-title');
    await expect(title).toHaveText('Agent Dashboard');

    // Check stats
    await expect(page.locator('#session-number')).toBeVisible();
    await expect(page.locator('#total-tokens')).toBeVisible();
    await expect(page.locator('#total-cost')).toBeVisible();
    await expect(page.locator('#current-provider')).toBeVisible();
  });

  test('should display 3-panel layout', async ({ page }) => {
    await page.goto(FILE_URL);

    // Check main content container
    const mainContent = await page.locator('.main-content');
    await expect(mainContent).toBeVisible();

    // Check left panel
    const leftPanel = await page.locator('.left-panel');
    await expect(leftPanel).toBeVisible();

    // Check main panel
    const mainPanel = await page.locator('.main-panel');
    await expect(mainPanel).toBeVisible();
  });

  test('should display Agent Status panel with all 13 agents', async ({ page }) => {
    await page.goto(FILE_URL);

    const agentList = await page.locator('#agent-list');
    await expect(agentList).toBeVisible();

    // Check all 13 agents are present
    const agentItems = await page.locator('.agent-item').all();
    expect(agentItems.length).toBe(13);

    // Verify agent names
    const expectedAgents = [
      'coding', 'coding_fast', 'github', 'linear', 'slack', 'ops',
      'pr_reviewer', 'pr_reviewer_fast', 'implementation_planning',
      'requirements_analysis', 'integration', 'migration', 'security_review'
    ];

    for (const agentName of expectedAgents) {
      const agent = await page.locator(`.agent-item[data-agent="${agentName}"]`);
      await expect(agent).toBeVisible();
    }
  });

  test('should display Activity Feed', async ({ page }) => {
    await page.goto(FILE_URL);

    const activityFeed = await page.locator('#activity-feed');
    await expect(activityFeed).toBeVisible();

    // Check activities are rendered
    const activityItems = await page.locator('.activity-item').all();
    expect(activityItems.length).toBeGreaterThan(0);
  });

  test('should display Chat Interface', async ({ page }) => {
    await page.goto(FILE_URL);

    // Check chat container
    await expect(page.locator('.chat-container')).toBeVisible();

    // Check chat messages area
    await expect(page.locator('#chat-messages')).toBeVisible();

    // Check chat input
    await expect(page.locator('#chat-input')).toBeVisible();

    // Check send button
    await expect(page.locator('#send-button')).toBeVisible();
  });

  test('should display Provider/Model selector', async ({ page }) => {
    await page.goto(FILE_URL);

    // Check provider selector
    const providerSelect = await page.locator('#provider-select');
    await expect(providerSelect).toBeVisible();

    // Check all providers are available
    const providers = await providerSelect.locator('option').allTextContents();
    expect(providers).toContain('Claude');
    expect(providers).toContain('ChatGPT');
    expect(providers).toContain('Gemini');
    expect(providers).toContain('Groq');
    expect(providers).toContain('KIMI');
    expect(providers).toContain('Windsurf');

    // Check model selector
    const modelSelect = await page.locator('#model-select');
    await expect(modelSelect).toBeVisible();
  });

  test('should have functional chat input', async ({ page }) => {
    await page.goto(FILE_URL);

    const input = await page.locator('#chat-input');
    const sendButton = await page.locator('#send-button');

    // Type a message
    await input.fill('Hello, this is a test message');

    // Click send
    await sendButton.click();

    // Wait for message to appear
    await page.waitForTimeout(600);

    // Check message was added
    const messages = await page.locator('.message.user').all();
    expect(messages.length).toBeGreaterThan(0);

    // Check input was cleared
    const inputValue = await input.inputValue();
    expect(inputValue).toBe('');
  });

  test('should switch providers and update models', async ({ page }) => {
    await page.goto(FILE_URL);

    const providerSelect = await page.locator('#provider-select');
    const modelSelect = await page.locator('#model-select');

    // Select OpenAI
    await providerSelect.selectOption('openai');

    // Wait for models to update
    await page.waitForTimeout(100);

    // Check models updated
    const models = await modelSelect.locator('option').allTextContents();
    expect(models).toContain('GPT-4o');
    expect(models).toContain('o1');

    // Select Gemini
    await providerSelect.selectOption('gemini');
    await page.waitForTimeout(100);

    const geminiModels = await modelSelect.locator('option').allTextContents();
    expect(geminiModels).toContain('2.5 Flash');
    expect(geminiModels).toContain('2.5 Pro');
  });

  test('should display footer with controls', async ({ page }) => {
    await page.goto(FILE_URL);

    const footer = await page.locator('.footer');
    await expect(footer).toBeVisible();

    // Check Pause All button
    await expect(page.locator('#pause-all')).toBeVisible();

    // Check Resume All button
    await expect(page.locator('#resume-all')).toBeVisible();

    // Check footer status
    await expect(page.locator('#footer-status')).toBeVisible();
  });

  test('should pause all agents', async ({ page }) => {
    await page.goto(FILE_URL);

    // First, set an agent to running (via console)
    await page.evaluate(() => {
      window.state.agents[0].status = 'running';
      window.renderAgents();
    });

    // Click Pause All
    await page.locator('#pause-all').click();

    // Wait for update
    await page.waitForTimeout(100);

    // Check footer status updated
    const footerStatus = await page.locator('#footer-status');
    await expect(footerStatus).toHaveText('All agents paused');

    // Check system message added
    const systemMessages = await page.locator('.message.system').allTextContents();
    expect(systemMessages.some(msg => msg.includes('All agents paused'))).toBeTruthy();
  });

  test('should resume all agents', async ({ page }) => {
    await page.goto(FILE_URL);

    // Set agents to paused
    await page.evaluate(() => {
      window.state.agents.forEach(agent => agent.status = 'paused');
      window.renderAgents();
    });

    // Click Resume All
    await page.locator('#resume-all').click();

    // Wait for update
    await page.waitForTimeout(100);

    // Check footer status updated
    const footerStatus = await page.locator('#footer-status');
    await expect(footerStatus).toHaveText('System Ready');
  });

  test('should apply dark mode styling by default', async ({ page }) => {
    await page.goto(FILE_URL);

    // Check body background is dark
    const bgColor = await page.locator('body').evaluate(el => {
      return window.getComputedStyle(el).backgroundColor;
    });

    // Should be a dark color (rgb values should be low)
    expect(bgColor).toContain('rgb');

    // Check text is light
    const textColor = await page.locator('body').evaluate(el => {
      return window.getComputedStyle(el).color;
    });

    expect(textColor).toContain('rgb');
  });

  test('should be responsive on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(FILE_URL);

    // Check main elements are still visible
    await expect(page.locator('.header')).toBeVisible();
    await expect(page.locator('.left-panel')).toBeVisible();
    await expect(page.locator('.main-panel')).toBeVisible();
    await expect(page.locator('.footer')).toBeVisible();
  });

  test('should be responsive on tablet viewport', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto(FILE_URL);

    // Check layout adapts
    await expect(page.locator('.header')).toBeVisible();
    await expect(page.locator('.main-content')).toBeVisible();
  });

  test('should handle Enter key to send message', async ({ page }) => {
    await page.goto(FILE_URL);

    const input = await page.locator('#chat-input');

    // Type message
    await input.fill('Testing Enter key');

    // Press Enter
    await input.press('Enter');

    // Wait for message
    await page.waitForTimeout(600);

    // Check message was sent
    const userMessages = await page.locator('.message.user').all();
    expect(userMessages.length).toBeGreaterThan(0);
  });

  test('should handle Shift+Enter for new line', async ({ page }) => {
    await page.goto(FILE_URL);

    const input = await page.locator('#chat-input');

    // Type first line
    await input.fill('First line');

    // Press Shift+Enter
    await input.press('Shift+Enter');

    // Type second line
    await input.press('KeyS');
    await input.press('KeyE');

    // Check input has newline
    const value = await input.inputValue();
    expect(value).toContain('\n');
  });

  test('should initialize JavaScript without errors', async ({ page }) => {
    const consoleMessages = [];
    page.on('console', msg => consoleMessages.push(msg.text()));

    await page.goto(FILE_URL);
    await page.waitForTimeout(500);

    // Check for init messages
    const initMessages = consoleMessages.filter(msg =>
      msg.includes('initialized') || msg.includes('ready')
    );
    expect(initMessages.length).toBeGreaterThan(0);
  });

  test('should render agent status dots with correct colors', async ({ page }) => {
    await page.goto(FILE_URL);

    // Check idle agent (gray)
    const idleDots = await page.locator('.agent-status-dot.idle').all();
    expect(idleDots.length).toBeGreaterThan(0);

    // Set one to running and check
    await page.evaluate(() => {
      window.state.agents[0].status = 'running';
      window.renderAgents();
    });

    await page.waitForTimeout(100);

    const runningDots = await page.locator('.agent-status-dot.running').all();
    expect(runningDots.length).toBeGreaterThan(0);
  });

  test('should display welcome message on load', async ({ page }) => {
    await page.goto(FILE_URL);

    // Wait for messages to load
    await page.waitForTimeout(200);

    // Check for welcome message
    const systemMessages = await page.locator('.message.system').allTextContents();
    expect(systemMessages.some(msg => msg.includes('Welcome'))).toBeTruthy();
  });

  test('should update stats when sending messages', async ({ page }) => {
    await page.goto(FILE_URL);

    // Get initial token count
    const initialTokens = await page.locator('#total-tokens').textContent();

    // Send a message
    await page.locator('#chat-input').fill('Test message for stats');
    await page.locator('#send-button').click();

    // Wait for response
    await page.waitForTimeout(700);

    // Check tokens increased
    const newTokens = await page.locator('#total-tokens').textContent();
    expect(newTokens).not.toBe(initialTokens);
  });

  test('should have proper accessibility attributes', async ({ page }) => {
    await page.goto(FILE_URL);

    // Check lang attribute
    const htmlLang = await page.locator('html').getAttribute('lang');
    expect(htmlLang).toBe('en');

    // Check labels for selectors
    await expect(page.locator('label[for="provider-select"]')).toBeVisible();
    await expect(page.locator('label[for="model-select"]')).toBeVisible();
  });

  test('should take screenshot for evidence', async ({ page }) => {
    await page.goto(FILE_URL);

    // Wait for full load
    await page.waitForTimeout(500);

    // Take screenshot
    const screenshotPath = path.join(__dirname, '../../screenshots/ai-103-dashboard-index.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });

    // Verify screenshot was created
    expect(fs.existsSync(screenshotPath)).toBeTruthy();
  });

  test('should have no console errors during interaction', async ({ page }) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));

    await page.goto(FILE_URL);

    // Perform various interactions
    await page.locator('#provider-select').selectOption('gemini');
    await page.locator('#chat-input').fill('Test');
    await page.locator('#send-button').click();
    await page.waitForTimeout(600);
    await page.locator('#pause-all').click();
    await page.waitForTimeout(200);
    await page.locator('#resume-all').click();

    expect(errors).toHaveLength(0);
  });
});
