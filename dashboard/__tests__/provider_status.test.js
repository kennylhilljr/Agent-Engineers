/**
 * Provider Status Indicators Tests - AI-73
 * Comprehensive test suite for AI Provider Status functionality
 */

describe('Provider Status Indicators - AI-73', () => {
    let chatInterface;
    let providerSelector;
    let providerStatusIndicator;
    let statusDot;
    let statusText;

    // Mock fetch
    global.fetch = jest.fn();

    // Mock sessionStorage
    let sessionStorageMock = {};

    beforeEach(() => {
        // Reset mocks
        jest.clearAllMocks();
        sessionStorageMock = {};

        // Mock sessionStorage
        global.sessionStorage = {
            getItem: jest.fn((key) => sessionStorageMock[key] || null),
            setItem: jest.fn((key, value) => {
                sessionStorageMock[key] = value;
            }),
            removeItem: jest.fn((key) => {
                delete sessionStorageMock[key];
            }),
            clear: jest.fn(() => {
                sessionStorageMock = {};
            })
        };

        // Setup DOM elements
        document.body.innerHTML = `
            <div id="chat-container" class="chat-container">
                <div class="provider-selector-container">
                    <label for="ai-provider-selector" class="provider-selector-label">
                        AI Provider:
                    </label>
                    <select
                        id="ai-provider-selector"
                        class="provider-selector"
                        data-testid="ai-provider-selector"
                        aria-label="Select AI Provider"
                    >
                        <option value="claude" data-testid="provider-option-claude">Claude</option>
                        <option value="chatgpt" data-testid="provider-option-chatgpt">ChatGPT</option>
                        <option value="gemini" data-testid="provider-option-gemini">Gemini</option>
                        <option value="groq" data-testid="provider-option-groq">Groq</option>
                        <option value="kimi" data-testid="provider-option-kimi">KIMI</option>
                        <option value="windsurf" data-testid="provider-option-windsurf">Windsurf</option>
                    </select>
                    <div class="provider-status-indicator" id="provider-status-indicator" data-testid="provider-status-indicator">
                        <span class="status-dot" data-testid="status-dot"></span>
                        <span class="status-text" data-testid="status-text">Checking...</span>
                    </div>
                    <span class="provider-badge" id="provider-badge" data-testid="provider-badge">Claude</span>
                </div>
                <div class="model-selector-container">
                    <label for="ai-model-selector" class="model-selector-label">Model:</label>
                    <select id="ai-model-selector" class="model-selector" data-testid="ai-model-selector">
                        <option value="haiku-4.5">Haiku 4.5</option>
                    </select>
                    <span class="model-badge" id="model-badge" data-testid="model-badge">Haiku 4.5</span>
                </div>
                <div id="chat-messages" class="chat-messages">
                    <div class="chat-welcome">
                        <p>Welcome to the Agent Dashboard Chat.</p>
                    </div>
                </div>
                <div class="chat-input-area">
                    <div class="chat-input-wrapper">
                        <input type="text" id="chat-input" class="chat-input" />
                        <button id="chat-send-btn" class="chat-send-btn">Send</button>
                    </div>
                </div>
            </div>
        `;

        // Mock API_BASE_URL
        global.API_BASE_URL = 'http://localhost:8080';

        // Initialize chat interface class
        class ChatInterface {
            constructor() {
                this.messagesContainer = document.getElementById('chat-messages');
                this.input = document.getElementById('chat-input');
                this.sendBtn = document.getElementById('chat-send-btn');
                this.providerSelector = document.getElementById('ai-provider-selector');
                this.providerBadge = document.getElementById('provider-badge');
                this.modelSelector = document.getElementById('ai-model-selector');
                this.modelBadge = document.getElementById('model-badge');
                this.providerStatusIndicator = document.getElementById('provider-status-indicator');
                this.messages = [];
                this.selectedProvider = 'claude';
                this.selectedModel = 'haiku-4.5';
                this.providerStatuses = {};

                this.providerModels = {
                    'claude': [
                        { id: 'haiku-4.5', name: 'Haiku 4.5', isDefault: true }
                    ]
                };
            }

            updateProviderBadge(provider) {
                if (!this.providerBadge) return;
                const providerNames = {
                    'claude': 'Claude',
                    'chatgpt': 'ChatGPT',
                    'gemini': 'Gemini',
                    'groq': 'Groq',
                    'kimi': 'KIMI',
                    'windsurf': 'Windsurf'
                };
                this.providerBadge.textContent = providerNames[provider] || provider;
            }

            handleProviderChange(event) {
                const newProvider = event.target.value;
                this.selectedProvider = newProvider;
                this.updateProviderBadge(newProvider);
                this.updateProviderStatusIndicator(newProvider);
            }

            async loadProviderStatus() {
                try {
                    const response = await fetch(`${API_BASE_URL}/api/providers/status`);
                    if (!response.ok) {
                        throw new Error(`Failed to fetch provider status: ${response.status}`);
                    }

                    const data = await response.json();
                    this.providerStatuses = data.providers;

                    // Update the status indicator for the currently selected provider
                    this.updateProviderStatusIndicator(this.selectedProvider);
                } catch (error) {
                    console.error('Error loading provider status:', error);
                    // Show error state if API fails
                    this.updateProviderStatusIndicator(this.selectedProvider, 'error', 'Unable to check status');
                }
            }

            updateProviderStatusIndicator(provider, forceStatus = null, forceMessage = null) {
                if (!this.providerStatusIndicator) return;

                const status = forceStatus || (this.providerStatuses[provider]?.status || 'unconfigured');
                const providerData = this.providerStatuses[provider] || {};

                // Update classes
                this.providerStatusIndicator.className = 'provider-status-indicator ' + status;
                this.providerStatusIndicator.setAttribute('data-status', status);

                // Update status text
                const statusText = this.providerStatusIndicator.querySelector('.status-text');
                if (statusText) {
                    if (forceMessage) {
                        statusText.textContent = forceMessage;
                    } else {
                        statusText.textContent = status === 'available' ? 'Available' :
                                                 status === 'unconfigured' ? 'Unconfigured' :
                                                 status === 'error' ? 'Error' : 'Unknown';
                    }
                }

                // Update tooltip
                let tooltip = this.providerStatusIndicator.querySelector('.tooltip');
                if (!tooltip) {
                    tooltip = document.createElement('div');
                    tooltip.className = 'tooltip';
                    tooltip.setAttribute('data-testid', 'status-tooltip');
                    this.providerStatusIndicator.appendChild(tooltip);
                }

                if (status === 'available') {
                    tooltip.textContent = `${providerData.name || provider} is configured and ready to use`;
                } else if (status === 'unconfigured') {
                    tooltip.textContent = providerData.setup_instructions || `Configure ${providerData.name || provider} API key`;
                } else if (status === 'error') {
                    tooltip.textContent = forceMessage || `${providerData.name || provider} is configured but unreachable`;
                }

                this.providerStatusIndicator.setAttribute('title', tooltip.textContent);
            }
        }

        chatInterface = new ChatInterface();
        providerSelector = document.getElementById('ai-provider-selector');
        providerStatusIndicator = document.getElementById('provider-status-indicator');
        statusDot = document.querySelector('.status-dot');
        statusText = document.querySelector('.status-text');

        // Set up event listener for provider change
        if (providerSelector) {
            providerSelector.addEventListener('change', (e) => chatInterface.handleProviderChange(e));
        }
    });

    describe('Status Indicator Initialization', () => {
        test('should have status indicator in DOM', () => {
            expect(providerStatusIndicator).toBeInTheDocument();
            expect(providerStatusIndicator).toHaveAttribute('data-testid', 'provider-status-indicator');
        });

        test('should have status dot element', () => {
            expect(statusDot).toBeInTheDocument();
            expect(statusDot).toHaveClass('status-dot');
        });

        test('should have status text element', () => {
            expect(statusText).toBeInTheDocument();
            expect(statusText).toHaveClass('status-text');
        });
    });

    describe('Available Status - Test Step 3', () => {
        beforeEach(() => {
            // Mock successful API response with configured provider
            global.fetch.mockResolvedValue({
                ok: true,
                json: async () => ({
                    providers: {
                        claude: {
                            status: 'available',
                            name: 'Claude',
                            configured: true,
                            setup_instructions: null
                        }
                    },
                    timestamp: '2026-02-16T10:00:00Z'
                })
            });
        });

        test('should show Available status when API key configured', async () => {
            await chatInterface.loadProviderStatus();

            expect(providerStatusIndicator).toHaveClass('available');
            expect(providerStatusIndicator).toHaveAttribute('data-status', 'available');
            expect(statusText).toHaveTextContent('Available');
        });

        test('should display green indicator for available status', async () => {
            await chatInterface.loadProviderStatus();

            expect(providerStatusIndicator).toHaveClass('available');
        });

        test('should show available tooltip message', async () => {
            await chatInterface.loadProviderStatus();

            const tooltip = providerStatusIndicator.querySelector('.tooltip');
            expect(tooltip).toBeInTheDocument();
            expect(tooltip).toHaveTextContent('Claude is configured and ready to use');
        });
    });

    describe('Unconfigured Status - Test Step 4', () => {
        beforeEach(() => {
            // Mock API response with unconfigured provider
            global.fetch.mockResolvedValue({
                ok: true,
                json: async () => ({
                    providers: {
                        chatgpt: {
                            status: 'unconfigured',
                            name: 'ChatGPT',
                            configured: false,
                            setup_instructions: 'Set OPENAI_API_KEY environment variable with your OpenAI API key'
                        }
                    },
                    timestamp: '2026-02-16T10:00:00Z'
                })
            });
        });

        test('should show Unconfigured status when API key missing', async () => {
            chatInterface.selectedProvider = 'chatgpt';
            await chatInterface.loadProviderStatus();

            expect(providerStatusIndicator).toHaveClass('unconfigured');
            expect(providerStatusIndicator).toHaveAttribute('data-status', 'unconfigured');
            expect(statusText).toHaveTextContent('Unconfigured');
        });

        test('should display gray indicator for unconfigured status', async () => {
            chatInterface.selectedProvider = 'chatgpt';
            await chatInterface.loadProviderStatus();

            expect(providerStatusIndicator).toHaveClass('unconfigured');
        });

        test('should show setup instructions in tooltip', async () => {
            chatInterface.selectedProvider = 'chatgpt';
            await chatInterface.loadProviderStatus();

            const tooltip = providerStatusIndicator.querySelector('.tooltip');
            expect(tooltip).toBeInTheDocument();
            expect(tooltip).toHaveTextContent('Set OPENAI_API_KEY environment variable');
        });
    });

    describe('Error Status - Test Step 6', () => {
        test('should show Error status when provider unreachable', async () => {
            // Mock API failure
            global.fetch.mockResolvedValue({
                ok: false,
                status: 500,
                json: async () => ({ error: 'Internal server error' })
            });

            await chatInterface.loadProviderStatus();

            expect(providerStatusIndicator).toHaveClass('error');
            expect(providerStatusIndicator).toHaveAttribute('data-status', 'error');
            expect(statusText).toHaveTextContent('Unable to check status');
        });

        test('should display red indicator for error status', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));

            await chatInterface.loadProviderStatus();

            expect(providerStatusIndicator).toHaveClass('error');
        });

        test('should show error tooltip message', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));

            await chatInterface.loadProviderStatus();

            const tooltip = providerStatusIndicator.querySelector('.tooltip');
            expect(tooltip).toBeInTheDocument();
            expect(tooltip).toHaveTextContent('Unable to check status');
        });
    });

    describe('Visual Distinction - Test Step 7', () => {
        test('should have distinct classes for each status state', async () => {
            // Test available
            chatInterface.updateProviderStatusIndicator('claude', 'available');
            expect(providerStatusIndicator).toHaveClass('available');
            expect(providerStatusIndicator).not.toHaveClass('unconfigured');
            expect(providerStatusIndicator).not.toHaveClass('error');

            // Test unconfigured
            chatInterface.updateProviderStatusIndicator('chatgpt', 'unconfigured');
            expect(providerStatusIndicator).toHaveClass('unconfigured');
            expect(providerStatusIndicator).not.toHaveClass('available');
            expect(providerStatusIndicator).not.toHaveClass('error');

            // Test error
            chatInterface.updateProviderStatusIndicator('gemini', 'error');
            expect(providerStatusIndicator).toHaveClass('error');
            expect(providerStatusIndicator).not.toHaveClass('available');
            expect(providerStatusIndicator).not.toHaveClass('unconfigured');
        });

        test('should update status text for each state', () => {
            chatInterface.updateProviderStatusIndicator('claude', 'available');
            expect(statusText).toHaveTextContent('Available');

            chatInterface.updateProviderStatusIndicator('chatgpt', 'unconfigured');
            expect(statusText).toHaveTextContent('Unconfigured');

            chatInterface.updateProviderStatusIndicator('gemini', 'error');
            expect(statusText).toHaveTextContent('Error');
        });
    });

    describe('Dynamic Updates - Test Step 8', () => {
        test('should update status when provider changes', async () => {
            // Setup initial status for claude
            global.fetch.mockResolvedValue({
                ok: true,
                json: async () => ({
                    providers: {
                        claude: {
                            status: 'available',
                            name: 'Claude',
                            configured: true
                        },
                        chatgpt: {
                            status: 'unconfigured',
                            name: 'ChatGPT',
                            configured: false,
                            setup_instructions: 'Set OPENAI_API_KEY'
                        }
                    }
                })
            });

            await chatInterface.loadProviderStatus();
            expect(providerStatusIndicator).toHaveClass('available');

            // Change provider
            providerSelector.value = 'chatgpt';
            providerSelector.dispatchEvent(new Event('change'));

            expect(providerStatusIndicator).toHaveClass('unconfigured');
        });

        test('should call API to fetch provider status', async () => {
            global.fetch.mockResolvedValue({
                ok: true,
                json: async () => ({
                    providers: {
                        claude: { status: 'available', name: 'Claude', configured: true }
                    }
                })
            });

            await chatInterface.loadProviderStatus();

            expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/api/providers/status');
        });
    });

    describe('All Providers Status - Test Step 2', () => {
        test('should support status for all 6 providers', async () => {
            global.fetch.mockResolvedValue({
                ok: true,
                json: async () => ({
                    providers: {
                        claude: { status: 'available', name: 'Claude', configured: true },
                        chatgpt: { status: 'unconfigured', name: 'ChatGPT', configured: false },
                        gemini: { status: 'unconfigured', name: 'Gemini', configured: false },
                        groq: { status: 'available', name: 'Groq', configured: true },
                        kimi: { status: 'unconfigured', name: 'KIMI', configured: false },
                        windsurf: { status: 'unconfigured', name: 'Windsurf', configured: false }
                    }
                })
            });

            await chatInterface.loadProviderStatus();

            expect(Object.keys(chatInterface.providerStatuses)).toHaveLength(6);
            expect(chatInterface.providerStatuses.claude).toBeDefined();
            expect(chatInterface.providerStatuses.chatgpt).toBeDefined();
            expect(chatInterface.providerStatuses.gemini).toBeDefined();
            expect(chatInterface.providerStatuses.groq).toBeDefined();
            expect(chatInterface.providerStatuses.kimi).toBeDefined();
            expect(chatInterface.providerStatuses.windsurf).toBeDefined();
        });
    });

    describe('Tooltip Functionality', () => {
        test('should create tooltip element when updating status', () => {
            chatInterface.updateProviderStatusIndicator('claude', 'available');

            const tooltip = providerStatusIndicator.querySelector('.tooltip');
            expect(tooltip).toBeInTheDocument();
            expect(tooltip).toHaveClass('tooltip');
            expect(tooltip).toHaveAttribute('data-testid', 'status-tooltip');
        });

        test('should update title attribute for accessibility', () => {
            chatInterface.updateProviderStatusIndicator('claude', 'available');

            expect(providerStatusIndicator).toHaveAttribute('title');
            expect(providerStatusIndicator.getAttribute('title')).toBeTruthy();
        });
    });

    describe('Edge Cases', () => {
        test('should handle missing provider data gracefully', () => {
            chatInterface.providerStatuses = {};
            chatInterface.updateProviderStatusIndicator('unknown-provider');

            expect(providerStatusIndicator).toHaveClass('unconfigured');
        });

        test('should handle API errors gracefully', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));

            await chatInterface.loadProviderStatus();

            expect(providerStatusIndicator).toHaveClass('error');
            expect(statusText).toHaveTextContent('Unable to check status');
        });

        test('should handle missing status indicator element', () => {
            chatInterface.providerStatusIndicator = null;

            // Should not throw error
            expect(() => {
                chatInterface.updateProviderStatusIndicator('claude');
            }).not.toThrow();
        });
    });
});
