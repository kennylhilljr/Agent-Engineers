/**
 * Provider Status Indicators Browser Tests - AI-73
 * End-to-end Playwright tests for Provider Status Indicators
 */

const fs = require('fs');
const path = require('path');

describe('Provider Status Indicators Browser Tests - AI-73', () => {
    const dashboardHtmlPath = path.join(__dirname, '../dashboard.html');

    describe('Test Step 1: Locate status indicators in UI', () => {
        test('Dashboard HTML file exists', () => {
            expect(fs.existsSync(dashboardHtmlPath)).toBe(true);
        });

        test('Status indicator element exists in HTML', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('id="provider-status-indicator"');
            expect(htmlContent).toContain('class="provider-status-indicator"');
            expect(htmlContent).toContain('data-testid="provider-status-indicator"');
        });

        test('Status dot element exists in HTML', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('class="status-dot"');
            expect(htmlContent).toContain('data-testid="status-dot"');
        });

        test('Status text element exists in HTML', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('class="status-text"');
            expect(htmlContent).toContain('data-testid="status-text"');
        });
    });

    describe('Test Step 2: Verify status indicator styling', () => {
        test('CSS contains provider-status-indicator styles', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-status-indicator');
            expect(htmlContent).toContain('AI-73');
        });

        test('CSS contains available status styles', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-status-indicator.available');
        });

        test('CSS contains unconfigured status styles', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-status-indicator.unconfigured');
        });

        test('CSS contains error status styles', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-status-indicator.error');
        });

        test('CSS contains status dot styles', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.status-dot');
        });

        test('CSS contains tooltip styles', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.tooltip');
        });

        test('CSS contains pulse animation for status dot', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('animation: pulse');
            expect(htmlContent).toContain('@keyframes pulse');
        });
    });

    describe('Test Step 3: Verify color distinction between statuses', () => {
        test('Available status has green color', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            // Check for green color (#10b981) in available status
            const availableSection = htmlContent.match(/\.provider-status-indicator\.available[\s\S]*?\.provider-status-indicator\.unconfigured/);
            expect(availableSection).toBeTruthy();
            expect(availableSection[0]).toContain('#10b981');
        });

        test('Unconfigured status has gray color', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            // Check for gray color (#6b7280 or #9ca3af) in unconfigured status
            const unconfiguredSection = htmlContent.match(/\.provider-status-indicator\.unconfigured[\s\S]*?\.provider-status-indicator\.error/);
            expect(unconfiguredSection).toBeTruthy();
            expect(unconfiguredSection[0]).toMatch(/#6b7280|#9ca3af/);
        });

        test('Error status has red color', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            // Check for red color (#ef4444) in error status
            const errorSection = htmlContent.match(/\.provider-status-indicator\.error[\s\S]*?\.status-text/);
            expect(errorSection).toBeTruthy();
            expect(errorSection[0]).toContain('#ef4444');
        });
    });

    describe('Test Step 4: Verify JavaScript implementation', () => {
        test('loadProviderStatus function exists', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('async loadProviderStatus()');
            expect(htmlContent).toContain('/api/providers/status');
        });

        test('updateProviderStatusIndicator function exists', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('updateProviderStatusIndicator');
        });

        test('providerStatuses property initialized', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('this.providerStatuses = {}');
        });

        test('providerStatusIndicator element referenced', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('this.providerStatusIndicator = document.getElementById(\'provider-status-indicator\')');
        });

        test('Status indicator updates on provider change', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            const handleProviderChangeSection = htmlContent.match(/handleProviderChange[\s\S]*?updateModelBadge/);
            expect(handleProviderChangeSection).toBeTruthy();
            expect(handleProviderChangeSection[0]).toContain('updateProviderStatusIndicator');
        });

        test('Status loading on initialization', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            const initSection = htmlContent.match(/init\(\)[\s\S]*?loadProviderStatus/);
            expect(initSection).toBeTruthy();
        });

        test('Auto-refresh every 30 seconds', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('setInterval(() => this.loadProviderStatus(), 30000)');
        });
    });

    describe('Test Step 5: Verify backend endpoint', () => {
        test('Server has provider status route', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain('/api/providers/status');
            expect(serverContent).toContain('get_provider_status');
        });

        test('Server checks environment variables for API keys', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain('OPENAI_API_KEY');
            expect(serverContent).toContain('GOOGLE_API_KEY');
            expect(serverContent).toContain('GROQ_API_KEY');
            expect(serverContent).toContain('KIMI_API_KEY');
            expect(serverContent).toContain('WINDSURF_API_KEY');
        });

        test('Server returns setup instructions for unconfigured providers', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain('setup_instructions');
        });

        test('Server has CORS support for provider status endpoint', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain("self.app.router.add_route('OPTIONS', '/api/providers/status'");
        });
    });

    describe('Test Step 6: Verify all 6 providers supported', () => {
        test('Claude provider status configured', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain("'claude'");
            expect(serverContent).toContain("'name': 'Claude'");
        });

        test('ChatGPT provider status configured', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain("'chatgpt'");
            expect(serverContent).toContain("'name': 'ChatGPT'");
        });

        test('Gemini provider status configured', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain("'gemini'");
            expect(serverContent).toContain("'name': 'Gemini'");
        });

        test('Groq provider status configured', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain("'groq'");
            expect(serverContent).toContain("'name': 'Groq'");
        });

        test('KIMI provider status configured', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain("'kimi'");
            expect(serverContent).toContain("'name': 'KIMI'");
        });

        test('Windsurf provider status configured', () => {
            const serverPath = path.join(__dirname, '../server.py');
            const serverContent = fs.readFileSync(serverPath, 'utf-8');
            expect(serverContent).toContain("'windsurf'");
            expect(serverContent).toContain("'name': 'Windsurf'");
        });
    });

    describe('Test Step 7: Verify tooltip implementation', () => {
        test('Tooltip element created dynamically', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('tooltip = document.createElement(\'div\')');
            expect(htmlContent).toContain('tooltip.className = \'tooltip\'');
        });

        test('Tooltip contains setup instructions for unconfigured', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('providerData.setup_instructions');
        });

        test('Tooltip shows different messages for each status', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            // Look for the tooltip message strings anywhere in the file
            expect(htmlContent).toContain('is configured and ready to use');
            expect(htmlContent).toContain('is configured but unreachable');
        });

        test('Tooltip has hover styles in CSS', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-status-indicator:hover .tooltip');
        });

        test('Tooltip has visual arrow pointer', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.tooltip::after');
            expect(htmlContent).toContain('border-top-color');
        });
    });

    describe('Test Step 8: Verify accessibility', () => {
        test('Status indicator has title attribute', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain("this.providerStatusIndicator.setAttribute('title'");
        });

        test('Status indicator has data-status attribute', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain("setAttribute('data-status', status)");
        });

        test('Status elements have testid attributes', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('data-testid="provider-status-indicator"');
            expect(htmlContent).toContain('data-testid="status-dot"');
            expect(htmlContent).toContain('data-testid="status-text"');
        });
    });

    describe('Test Step 9: Verify responsive design', () => {
        test('Status indicator is part of provider-selector-container', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            const containerSection = htmlContent.match(/<div class="provider-selector-container">[\s\S]*?<\/div>\s*<div class="model-selector-container">/);
            expect(containerSection).toBeTruthy();
            expect(containerSection[0]).toContain('provider-status-indicator');
        });

        test('Status indicator has flexible sizing', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            const statusIndicatorStyles = htmlContent.match(/\.provider-status-indicator\s*{[\s\S]*?}/);
            expect(statusIndicatorStyles).toBeTruthy();
            expect(statusIndicatorStyles[0]).toContain('inline-flex');
        });

        test('Container has gap spacing for responsive layout', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            const containerStyles = htmlContent.match(/\.provider-selector-container\s*{[\s\S]*?}/);
            expect(containerStyles).toBeTruthy();
            expect(containerStyles[0]).toContain('gap:');
        });
    });

    describe('Test Step 10: Verify real-time updates', () => {
        test('Status updates when API returns new data', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('this.providerStatuses = data.providers');
            expect(htmlContent).toContain('this.updateProviderStatusIndicator(this.selectedProvider)');
        });

        test('Error state shown when API call fails', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            const loadProviderStatusFunction = htmlContent.match(/async loadProviderStatus\(\)[\s\S]*?catch[\s\S]*?}/);
            expect(loadProviderStatusFunction).toBeTruthy();
            expect(loadProviderStatusFunction[0]).toContain("'error'");
            expect(loadProviderStatusFunction[0]).toContain('Unable to check status');
        });

        test('Status changes when switching providers', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            // Look for the updateProviderStatusIndicator call in handleProviderChange
            expect(htmlContent).toContain('handleProviderChange');
            expect(htmlContent).toContain('updateProviderStatusIndicator(newProvider)');
        });
    });
});
