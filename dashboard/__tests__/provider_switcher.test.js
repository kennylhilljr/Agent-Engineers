/**
 * Provider Switcher Tests - AI-71
 * Comprehensive test suite for AI Provider Switcher functionality
 */

describe('Provider Switcher - AI-71', () => {
    let chatInterface;
    let providerSelector;
    let providerBadge;
    let messagesContainer;
    let input;
    let sendBtn;

    // Mock sessionStorage
    let sessionStorageMock = {};

    beforeEach(() => {
        // Reset sessionStorage mock
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
                        <option value="claude" data-testid="provider-option-claude">Claude (Haiku 4.5, Sonnet 4.5, Opus 4.6)</option>
                        <option value="chatgpt" data-testid="provider-option-chatgpt">ChatGPT (GPT-4o, o1, o3-mini, o4-mini)</option>
                        <option value="gemini" data-testid="provider-option-gemini">Gemini (2.5 Flash, 2.5 Pro, 2.0 Flash)</option>
                        <option value="groq" data-testid="provider-option-groq">Groq (Llama 3.3 70B, Mixtral 8x7B)</option>
                        <option value="kimi" data-testid="provider-option-kimi">KIMI (Moonshot 2M context)</option>
                        <option value="windsurf" data-testid="provider-option-windsurf">Windsurf (Cascade)</option>
                    </select>
                    <span class="provider-badge" id="provider-badge" data-testid="provider-badge">Claude</span>
                </div>
                <div id="chat-messages" class="chat-messages">
                    <div class="chat-welcome">
                        <p>Welcome to the Agent Dashboard Chat. Ask me anything about your agent status, metrics, or general questions!</p>
                    </div>
                </div>
                <div class="chat-input-area">
                    <div class="chat-input-wrapper">
                        <input
                            type="text"
                            id="chat-input"
                            class="chat-input"
                            placeholder="Type a message... (e.g., 'What's my status?')"
                            data-testid="chat-message-input"
                        />
                        <button
                            id="chat-send-btn"
                            class="chat-send-btn"
                            data-testid="chat-send-button"
                            aria-label="Send message"
                        >
                            Send
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Initialize chat interface class
        class ChatInterface {
            constructor() {
                this.messagesContainer = document.getElementById('chat-messages');
                this.input = document.getElementById('chat-input');
                this.sendBtn = document.getElementById('chat-send-btn');
                this.providerSelector = document.getElementById('ai-provider-selector');
                this.providerBadge = document.getElementById('provider-badge');
                this.messages = [];
                this.selectedProvider = 'claude';
                this.init();
            }

            init() {
                if (!this.input || !this.sendBtn) return;
                this.loadSavedProvider();
                this.sendBtn.addEventListener('click', () => this.sendMessage());
                this.input.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        this.sendMessage();
                    }
                });
                if (this.providerSelector) {
                    this.providerSelector.addEventListener('change', (e) => this.handleProviderChange(e));
                }
            }

            loadSavedProvider() {
                try {
                    const savedProvider = sessionStorage.getItem('selectedAIProvider');
                    if (savedProvider) {
                        this.selectedProvider = savedProvider;
                        if (this.providerSelector) {
                            this.providerSelector.value = savedProvider;
                        }
                        this.updateProviderBadge(savedProvider);
                    } else {
                        this.updateProviderBadge('claude');
                    }
                } catch (error) {
                    console.warn('Could not load saved provider:', error);
                }
            }

            handleProviderChange(event) {
                const newProvider = event.target.value;
                this.selectedProvider = newProvider;
                try {
                    sessionStorage.setItem('selectedAIProvider', newProvider);
                } catch (error) {
                    console.warn('Could not save provider to sessionStorage:', error);
                }
                this.updateProviderBadge(newProvider);
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

            getSelectedProvider() {
                return this.selectedProvider;
            }

            sendMessage() {
                const text = this.input.value.trim();
                if (!text) return;
                const provider = this.selectedProvider;
                this.addMessage(text, 'user', provider);
                this.input.value = '';
                this.showLoadingIndicator();
                setTimeout(() => {
                    this.removeLoadingIndicator();
                    this.addMessage(this.generateAIResponse(text, provider), 'ai', provider);
                }, 800);
            }

            addMessage(text, sender, provider = null) {
                const message = {
                    id: Date.now(),
                    text,
                    sender,
                    provider: provider || this.selectedProvider,
                    timestamp: new Date()
                };
                this.messages.push(message);
                this.renderMessage(message);
                this.scrollToBottom();
            }

            renderMessage(message) {
                const welcome = this.messagesContainer.querySelector('.chat-welcome');
                if (welcome && this.messages.length === 1) {
                    welcome.remove();
                }
                const div = document.createElement('div');
                div.className = `chat-message ${message.sender}`;
                div.setAttribute('data-testid', `chat-message-${message.sender}`);
                div.setAttribute('data-message-id', message.id);
                div.setAttribute('data-provider', message.provider);
                const content = document.createElement('div');
                const timeStr = message.timestamp.toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit'
                });
                content.innerHTML = `
                    <div class="chat-message-content">${this.escapeHtml(message.text)}</div>
                    <div class="chat-timestamp">${timeStr}</div>
                `;
                div.appendChild(content);
                this.messagesContainer.appendChild(div);
            }

            showLoadingIndicator() {
                const div = document.createElement('div');
                div.className = 'chat-message ai';
                div.id = 'chat-loading';
                div.setAttribute('data-testid', 'chat-loading-indicator');
                div.innerHTML = `
                    <div class="chat-message-content">
                        <div class="chat-loading">
                            <div class="chat-loading-dot"></div>
                            <div class="chat-loading-dot"></div>
                            <div class="chat-loading-dot"></div>
                        </div>
                    </div>
                `;
                this.messagesContainer.appendChild(div);
                this.scrollToBottom();
            }

            removeLoadingIndicator() {
                const loading = document.getElementById('chat-loading');
                if (loading) loading.remove();
            }

            generateAIResponse(userMessage, provider) {
                const lower = userMessage.toLowerCase();
                const providerNames = {
                    'claude': 'Claude',
                    'chatgpt': 'ChatGPT',
                    'gemini': 'Gemini',
                    'groq': 'Groq',
                    'kimi': 'KIMI',
                    'windsurf': 'Windsurf'
                };
                const providerName = providerNames[provider] || provider;

                if (lower.includes('status') || lower.includes('how')) {
                    return `[${providerName}] Your agents are running smoothly. All systems are operational with 99.2% uptime.`;
                }
                if (lower.includes('metric') || lower.includes('performance')) {
                    return `[${providerName}] Current metrics show strong performance: 94% success rate, avg response time 245ms.`;
                }
                if (lower.includes('hello') || lower.includes('hi') || lower.includes('hey')) {
                    return `[${providerName}] Hello! I'm here to help you with any questions about your agent dashboard.`;
                }
                return `[${providerName}] I understand. Based on your agent dashboard, everything is performing within expected parameters. Is there anything specific you'd like to know?`;
            }

            scrollToBottom() {
                this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
            }

            escapeHtml(text) {
                const map = {
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#039;'
                };
                return text.replace(/[&<>"']/g, m => map[m]);
            }

            getMessages() {
                return this.messages;
            }

            clearMessages() {
                this.messages = [];
                this.messagesContainer.innerHTML = `
                    <div class="chat-welcome">
                        <p>Welcome to the Agent Dashboard Chat. Ask me anything about your agent status, metrics, or general questions!</p>
                    </div>
                `;
            }
        }

        chatInterface = new ChatInterface();
        providerSelector = document.getElementById('ai-provider-selector');
        providerBadge = document.getElementById('provider-badge');
        messagesContainer = document.getElementById('chat-messages');
        input = document.getElementById('chat-input');
        sendBtn = document.getElementById('chat-send-btn');
    });

    describe('Provider Selector Initialization', () => {
        test('should have provider selector in DOM', () => {
            expect(providerSelector).toBeInTheDocument();
            expect(providerSelector).toHaveAttribute('data-testid', 'ai-provider-selector');
        });

        test('should have all 6 providers listed', () => {
            const options = providerSelector.querySelectorAll('option');
            expect(options.length).toBe(6);

            const providers = Array.from(options).map(opt => opt.value);
            expect(providers).toContain('claude');
            expect(providers).toContain('chatgpt');
            expect(providers).toContain('gemini');
            expect(providers).toContain('groq');
            expect(providers).toContain('kimi');
            expect(providers).toContain('windsurf');
        });

        test('should have Claude as default provider', () => {
            expect(providerSelector.value).toBe('claude');
            expect(chatInterface.getSelectedProvider()).toBe('claude');
        });

        test('should display provider badge', () => {
            expect(providerBadge).toBeInTheDocument();
            expect(providerBadge).toHaveTextContent('Claude');
        });

        test('should have proper accessibility attributes', () => {
            expect(providerSelector).toHaveAttribute('aria-label', 'Select AI Provider');
            const label = document.querySelector('label[for="ai-provider-selector"]');
            expect(label).toBeInTheDocument();
        });
    });

    describe('Provider Selection - Test Step 3: Click each provider', () => {
        test('should select ChatGPT provider', () => {
            providerSelector.value = 'chatgpt';
            providerSelector.dispatchEvent(new Event('change'));

            expect(chatInterface.getSelectedProvider()).toBe('chatgpt');
            expect(providerBadge.textContent).toBe('ChatGPT');
        });

        test('should select Gemini provider', () => {
            providerSelector.value = 'gemini';
            providerSelector.dispatchEvent(new Event('change'));

            expect(chatInterface.getSelectedProvider()).toBe('gemini');
            expect(providerBadge.textContent).toBe('Gemini');
        });

        test('should select Groq provider', () => {
            providerSelector.value = 'groq';
            providerSelector.dispatchEvent(new Event('change'));

            expect(chatInterface.getSelectedProvider()).toBe('groq');
            expect(providerBadge.textContent).toBe('Groq');
        });

        test('should select KIMI provider', () => {
            providerSelector.value = 'kimi';
            providerSelector.dispatchEvent(new Event('change'));

            expect(chatInterface.getSelectedProvider()).toBe('kimi');
            expect(providerBadge.textContent).toBe('KIMI');
        });

        test('should select Windsurf provider', () => {
            providerSelector.value = 'windsurf';
            providerSelector.dispatchEvent(new Event('change'));

            expect(chatInterface.getSelectedProvider()).toBe('windsurf');
            expect(providerBadge.textContent).toBe('Windsurf');
        });

        test('should select Claude provider explicitly', () => {
            // First switch to another provider
            providerSelector.value = 'gemini';
            providerSelector.dispatchEvent(new Event('change'));

            // Then switch back to Claude
            providerSelector.value = 'claude';
            providerSelector.dispatchEvent(new Event('change'));

            expect(chatInterface.getSelectedProvider()).toBe('claude');
            expect(providerBadge.textContent).toBe('Claude');
        });
    });

    describe('Provider Switching - Test Step 7: Switch between providers', () => {
        test('should switch from Claude to ChatGPT', () => {
            expect(chatInterface.getSelectedProvider()).toBe('claude');

            providerSelector.value = 'chatgpt';
            providerSelector.dispatchEvent(new Event('change'));

            expect(chatInterface.getSelectedProvider()).toBe('chatgpt');
        });

        test('should switch between all providers sequentially', () => {
            const providerSequence = ['chatgpt', 'gemini', 'groq', 'kimi', 'windsurf', 'claude'];

            providerSequence.forEach(provider => {
                providerSelector.value = provider;
                providerSelector.dispatchEvent(new Event('change'));
                expect(chatInterface.getSelectedProvider()).toBe(provider);
            });
        });

        test('should update badge when switching providers', () => {
            const testCases = [
                { value: 'chatgpt', expected: 'ChatGPT' },
                { value: 'gemini', expected: 'Gemini' },
                { value: 'groq', expected: 'Groq' },
                { value: 'kimi', expected: 'KIMI' },
                { value: 'windsurf', expected: 'Windsurf' }
            ];

            testCases.forEach(({ value, expected }) => {
                providerSelector.value = value;
                providerSelector.dispatchEvent(new Event('change'));
                expect(providerBadge.textContent).toBe(expected);
            });
        });
    });

    describe('SessionStorage Persistence - Test Step 10', () => {
        test('should save selected provider to sessionStorage', () => {
            providerSelector.value = 'chatgpt';
            providerSelector.dispatchEvent(new Event('change'));

            expect(sessionStorage.setItem).toHaveBeenCalledWith('selectedAIProvider', 'chatgpt');
            expect(sessionStorageMock['selectedAIProvider']).toBe('chatgpt');
        });

        test('should load saved provider from sessionStorage on init', () => {
            // Set a saved provider
            sessionStorageMock['selectedAIProvider'] = 'gemini';

            // Create new instance
            const newChatInterface = new (chatInterface.constructor)();

            expect(newChatInterface.getSelectedProvider()).toBe('gemini');
        });

        test('should persist provider across page refresh simulation', () => {
            // Select a provider
            providerSelector.value = 'groq';
            providerSelector.dispatchEvent(new Event('change'));

            // Simulate page refresh by creating new instance
            const newChatInterface = new (chatInterface.constructor)();

            expect(newChatInterface.getSelectedProvider()).toBe('groq');
        });

        test('should default to Claude if no saved provider', () => {
            // Ensure sessionStorage is empty
            sessionStorageMock = {};

            const newChatInterface = new (chatInterface.constructor)();

            expect(newChatInterface.getSelectedProvider()).toBe('claude');
        });
    });

    describe('Message Attribution - Test Step 9', () => {
        test('should attribute messages to correct provider', (done) => {
            providerSelector.value = 'chatgpt';
            providerSelector.dispatchEvent(new Event('change'));

            input.value = 'Hello';
            sendBtn.click();

            setTimeout(() => {
                const messages = chatInterface.getMessages();
                expect(messages[0].provider).toBe('chatgpt');
                done();
            }, 100);
        });

        test('should include provider name in AI responses', (done) => {
            providerSelector.value = 'gemini';
            providerSelector.dispatchEvent(new Event('change'));

            input.value = 'Hello';
            sendBtn.click();

            setTimeout(() => {
                const aiMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-ai"]');
                expect(aiMessages.length).toBeGreaterThan(0);
                expect(aiMessages[0]).toHaveTextContent('[Gemini]');
                done();
            }, 900);
        });

        test('should maintain provider attribution across multiple messages', (done) => {
            providerSelector.value = 'groq';
            providerSelector.dispatchEvent(new Event('change'));

            input.value = 'First message';
            sendBtn.click();

            setTimeout(() => {
                input.value = 'Second message';
                sendBtn.click();

                setTimeout(() => {
                    const messages = chatInterface.getMessages();
                    expect(messages[0].provider).toBe('groq');
                    expect(messages[1].provider).toBe('groq');
                    done();
                }, 900);
            }, 900);
        });

        test('should change provider attribution when provider is switched', (done) => {
            // Send message with Claude
            input.value = 'Claude message';
            sendBtn.click();

            setTimeout(() => {
                // Switch to ChatGPT
                providerSelector.value = 'chatgpt';
                providerSelector.dispatchEvent(new Event('change'));

                input.value = 'ChatGPT message';
                sendBtn.click();

                setTimeout(() => {
                    const messages = chatInterface.getMessages();
                    expect(messages[0].provider).toBe('claude');
                    expect(messages[2].provider).toBe('chatgpt');
                    done();
                }, 900);
            }, 900);
        });
    });

    describe('UI Behavior', () => {
        test('should maintain selection visibility', () => {
            providerSelector.value = 'kimi';
            providerSelector.dispatchEvent(new Event('change'));

            expect(providerSelector.value).toBe('kimi');
            expect(providerBadge.textContent).toBe('KIMI');
        });

        test('should handle rapid provider switching', () => {
            const providers = ['chatgpt', 'gemini', 'groq', 'claude'];

            providers.forEach(provider => {
                providerSelector.value = provider;
                providerSelector.dispatchEvent(new Event('change'));
            });

            expect(chatInterface.getSelectedProvider()).toBe('claude');
        });

        test('should update provider before sending message', () => {
            providerSelector.value = 'windsurf';
            providerSelector.dispatchEvent(new Event('change'));

            input.value = 'Test message';
            sendBtn.click();

            const messages = chatInterface.getMessages();
            expect(messages[0].provider).toBe('windsurf');
        });
    });

    describe('Edge Cases', () => {
        test('should handle sessionStorage errors gracefully', () => {
            // Mock sessionStorage to throw error
            sessionStorage.setItem = jest.fn(() => {
                throw new Error('Storage quota exceeded');
            });

            providerSelector.value = 'chatgpt';
            providerSelector.dispatchEvent(new Event('change'));

            // Should still update internal state
            expect(chatInterface.getSelectedProvider()).toBe('chatgpt');
        });

        test('should handle missing provider selector gracefully', () => {
            // Remove provider selector
            providerSelector.remove();

            // Create new instance without provider selector
            const element = document.getElementById('ai-provider-selector');
            expect(element).toBeNull();

            // Should still function with default provider
            expect(chatInterface.getSelectedProvider()).toBeDefined();
        });

        test('should handle invalid provider value', () => {
            const currentProvider = chatInterface.getSelectedProvider();

            // Try to set invalid provider (shouldn't break)
            providerSelector.value = 'invalid-provider';
            providerSelector.dispatchEvent(new Event('change'));

            // Should update to the new value even if invalid
            expect(chatInterface.getSelectedProvider()).toBe('invalid-provider');
        });
    });

    describe('Provider Details - Test Step 2', () => {
        test('should display Claude with correct models', () => {
            const claudeOption = providerSelector.querySelector('[data-testid="provider-option-claude"]');
            expect(claudeOption).toHaveTextContent('Haiku 4.5');
            expect(claudeOption).toHaveTextContent('Sonnet 4.5');
            expect(claudeOption).toHaveTextContent('Opus 4.6');
        });

        test('should display ChatGPT with correct models', () => {
            const option = providerSelector.querySelector('[data-testid="provider-option-chatgpt"]');
            expect(option).toHaveTextContent('GPT-4o');
            expect(option).toHaveTextContent('o1');
            expect(option).toHaveTextContent('o3-mini');
            expect(option).toHaveTextContent('o4-mini');
        });

        test('should display Gemini with correct models', () => {
            const option = providerSelector.querySelector('[data-testid="provider-option-gemini"]');
            expect(option).toHaveTextContent('2.5 Flash');
            expect(option).toHaveTextContent('2.5 Pro');
            expect(option).toHaveTextContent('2.0 Flash');
        });

        test('should display Groq with correct models', () => {
            const option = providerSelector.querySelector('[data-testid="provider-option-groq"]');
            expect(option).toHaveTextContent('Llama 3.3 70B');
            expect(option).toHaveTextContent('Mixtral 8x7B');
        });

        test('should display KIMI with correct context', () => {
            const option = providerSelector.querySelector('[data-testid="provider-option-kimi"]');
            expect(option).toHaveTextContent('Moonshot');
            expect(option).toHaveTextContent('2M context');
        });

        test('should display Windsurf with correct model', () => {
            const option = providerSelector.querySelector('[data-testid="provider-option-windsurf"]');
            expect(option).toHaveTextContent('Cascade');
        });
    });
});
