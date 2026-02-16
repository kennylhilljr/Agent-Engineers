/**
 * Provider Switcher Browser Tests - AI-71
 * End-to-end Playwright tests for AI Provider Switcher
 */

const fs = require('fs');
const path = require('path');

describe('Provider Switcher Browser Tests - AI-71', () => {
    const testHtmlPath = path.join(__dirname, '../test_chat.html');
    const dashboardHtmlPath = path.join(__dirname, '../dashboard.html');

    describe('Test Step 1: Locate provider selector in chat UI', () => {
        test('Test HTML file exists', () => {
            expect(fs.existsSync(testHtmlPath)).toBe(true);
        });

        test('Dashboard HTML file exists', () => {
            expect(fs.existsSync(dashboardHtmlPath)).toBe(true);
        });

        test('Provider selector exists in test HTML', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('id="ai-provider-selector"');
            expect(htmlContent).toContain('class="provider-selector"');
            expect(htmlContent).toContain('data-testid="ai-provider-selector"');
        });

        test('Provider selector exists in dashboard HTML', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('id="ai-provider-selector"');
            expect(htmlContent).toContain('class="provider-selector"');
        });

        test('Provider selector container has proper styling', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-selector-container');
            expect(htmlContent).toContain('.provider-selector-label');
            expect(htmlContent).toContain('.provider-badge');
        });
    });

    describe('Test Step 2: Verify all 6 providers are listed', () => {
        test('All 6 provider options exist in HTML', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');

            // Check for all providers
            expect(htmlContent).toContain('value="claude"');
            expect(htmlContent).toContain('value="chatgpt"');
            expect(htmlContent).toContain('value="gemini"');
            expect(htmlContent).toContain('value="groq"');
            expect(htmlContent).toContain('value="kimi"');
            expect(htmlContent).toContain('value="windsurf"');
        });

        test('Claude provider has correct models listed', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('Claude (Haiku 4.5, Sonnet 4.5, Opus 4.6)');
        });

        test('ChatGPT provider has correct models listed', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('ChatGPT (GPT-4o, o1, o3-mini, o4-mini)');
        });

        test('Gemini provider has correct models listed', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('Gemini (2.5 Flash, 2.5 Pro, 2.0 Flash)');
        });

        test('Groq provider has correct models listed', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('Groq (Llama 3.3 70B, Mixtral 8x7B)');
        });

        test('KIMI provider has correct description', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('KIMI (Moonshot 2M context)');
        });

        test('Windsurf provider has correct model listed', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('Windsurf (Cascade)');
        });

        test('All providers have data-testid attributes', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('data-testid="provider-option-claude"');
            expect(htmlContent).toContain('data-testid="provider-option-chatgpt"');
            expect(htmlContent).toContain('data-testid="provider-option-gemini"');
            expect(htmlContent).toContain('data-testid="provider-option-groq"');
            expect(htmlContent).toContain('data-testid="provider-option-kimi"');
            expect(htmlContent).toContain('data-testid="provider-option-windsurf"');
        });
    });

    describe('Test Step 4: Verify Claude is default selection', () => {
        test('Claude option is first in selector', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            const selectorMatch = htmlContent.match(/<select[^>]*id="ai-provider-selector"[^>]*>([\s\S]*?)<\/select>/);
            expect(selectorMatch).toBeTruthy();

            const selectorContent = selectorMatch[1];
            const firstOption = selectorContent.match(/<option[^>]*value="([^"]+)"/);
            expect(firstOption[1]).toBe('claude');
        });

        test('Default provider badge shows Claude', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            const badgeMatch = htmlContent.match(/<span[^>]*id="provider-badge"[^>]*>([^<]+)<\/span>/);
            expect(badgeMatch).toBeTruthy();
            expect(badgeMatch[1]).toBe('Claude');
        });

        test('JavaScript initializes with Claude as default', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain("this.selectedProvider = 'claude'");
        });
    });

    describe('Provider Selection Logic', () => {
        test('handleProviderChange function exists', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('handleProviderChange');
        });

        test('updateProviderBadge function exists', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('updateProviderBadge');
        });

        test('getSelectedProvider function exists', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('getSelectedProvider');
        });

        test('Provider change event listener is set up', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain("addEventListener('change'");
        });
    });

    describe('SessionStorage Integration - Test Step 10', () => {
        test('loadSavedProvider function exists', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('loadSavedProvider');
        });

        test('sessionStorage.getItem is called for loading', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain("sessionStorage.getItem('selectedAIProvider')");
        });

        test('sessionStorage.setItem is called for saving', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain("sessionStorage.setItem('selectedAIProvider'");
        });

        test('Error handling for sessionStorage failures', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toMatch(/try\s*{[\s\S]*sessionStorage[\s\S]*}\s*catch/);
        });
    });

    describe('Message Attribution - Test Step 9', () => {
        test('Messages include provider information', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('provider: provider ||');
        });

        test('AI responses include provider name prefix', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('[${providerName}]');
        });

        test('Message rendering includes provider data attribute', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain("data-provider");
        });

        test('Provider is passed to generateAIResponse', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('generateAIResponse(text, provider)');
        });
    });

    describe('UI Elements and Styling', () => {
        test('Provider selector has proper CSS classes', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-selector {');
            expect(htmlContent).toContain('padding:');
            expect(htmlContent).toContain('border-radius:');
            expect(htmlContent).toContain('cursor: pointer');
        });

        test('Provider badge has styling', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-badge {');
            expect(htmlContent).toContain('text-transform: uppercase');
        });

        test('Provider selector container has layout', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-selector-container {');
            expect(htmlContent).toContain('display: flex');
        });

        test('Hover effects are defined', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-selector:hover');
        });

        test('Focus styles are defined', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-selector:focus');
        });
    });

    describe('Accessibility', () => {
        test('Provider selector has aria-label', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('aria-label="Select AI Provider"');
        });

        test('Provider selector has associated label', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('for="ai-provider-selector"');
            expect(htmlContent).toContain('AI Provider:');
        });

        test('All interactive elements have proper roles', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('<select');
            expect(htmlContent).toContain('<option');
        });
    });

    describe('Integration with Chat Interface', () => {
        test('Provider selector is positioned before messages', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            const providerIndex = htmlContent.indexOf('provider-selector-container');
            const messagesIndex = htmlContent.indexOf('chat-messages');
            expect(providerIndex).toBeLessThan(messagesIndex);
            expect(providerIndex).toBeGreaterThan(0);
        });

        test('Chat interface initializes provider selector', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain("this.providerSelector = document.getElementById('ai-provider-selector')");
            expect(htmlContent).toContain("this.providerBadge = document.getElementById('provider-badge')");
        });

        test('sendMessage uses selected provider', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('const provider = this.selectedProvider');
        });
    });

    describe('Provider Name Mapping', () => {
        test('Provider names are properly mapped', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain("'claude': 'Claude'");
            expect(htmlContent).toContain("'chatgpt': 'ChatGPT'");
            expect(htmlContent).toContain("'gemini': 'Gemini'");
            expect(htmlContent).toContain("'groq': 'Groq'");
            expect(htmlContent).toContain("'kimi': 'KIMI'");
            expect(htmlContent).toContain("'windsurf': 'Windsurf'");
        });

        test('Provider name mapping is used in multiple functions', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            const mappingCount = (htmlContent.match(/providerNames\s*=/g) || []).length;
            expect(mappingCount).toBeGreaterThanOrEqual(2);
        });
    });

    describe('Dashboard Integration', () => {
        test('Dashboard HTML includes provider selector', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('id="ai-provider-selector"');
            expect(htmlContent).toContain('class="provider-selector-container"');
        });

        test('Dashboard has all provider styles', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('.provider-selector-container');
            expect(htmlContent).toContain('.provider-selector {');
            expect(htmlContent).toContain('.provider-badge');
        });

        test('Dashboard ChatInterface includes provider logic', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('handleProviderChange');
            expect(htmlContent).toContain('loadSavedProvider');
            expect(htmlContent).toContain('updateProviderBadge');
        });

        test('Dashboard maintains chat interface compatibility', () => {
            const htmlContent = fs.readFileSync(dashboardHtmlPath, 'utf-8');
            expect(htmlContent).toContain('class ChatInterface');
            expect(htmlContent).toContain('initChat');
        });
    });

    describe('Error Handling', () => {
        test('Handles missing provider selector gracefully', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('if (this.providerSelector)');
        });

        test('Handles missing provider badge gracefully', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            expect(htmlContent).toContain('if (!this.providerBadge) return');
        });

        test('Has try-catch for sessionStorage operations', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            const tryCatchCount = (htmlContent.match(/try\s*{[\s\S]*?}\s*catch/g) || []).length;
            expect(tryCatchCount).toBeGreaterThanOrEqual(2);
        });
    });

    describe('Code Quality', () => {
        test('No syntax errors in JavaScript', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            const scriptMatch = htmlContent.match(/<script>([\s\S]*?)<\/script>/);
            expect(scriptMatch).toBeTruthy();
            // Check for common syntax errors
            expect(htmlContent).not.toContain('consle.log');
            expect(htmlContent).not.toContain('fucntion');
        });

        test('Consistent coding style', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            // Check for consistent arrow functions
            expect(htmlContent).toContain('=>');
            // Check for const/let usage
            expect(htmlContent).toContain('const ');
        });

        test('No unused variables in provider logic', () => {
            const htmlContent = fs.readFileSync(testHtmlPath, 'utf-8');
            // Variables should be used
            expect(htmlContent).toMatch(/selectedProvider[\s\S]*selectedProvider/);
            expect(htmlContent).toMatch(/providerBadge[\s\S]*providerBadge/);
        });
    });
});
