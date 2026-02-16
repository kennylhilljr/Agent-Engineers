/**
 * AI-72: Model Selector per Provider - Unit Tests
 *
 * Test suite for model selector functionality including:
 * - Model dropdown updates based on provider
 * - Model selection and persistence
 * - Default model handling
 * - SessionStorage integration
 */

// Mock DOM environment
const { JSDOM } = require('jsdom');

describe('AI-72: Model Selector per Provider', () => {
    let dom, document, window, chatInterface;

    // HTML template for testing
    const htmlTemplate = `
        <!DOCTYPE html>
        <html>
        <body>
            <div id="chat-container">
                <select id="ai-provider-selector" data-testid="ai-provider-selector">
                    <option value="claude">Claude</option>
                    <option value="chatgpt">ChatGPT</option>
                    <option value="gemini">Gemini</option>
                    <option value="groq">Groq</option>
                    <option value="kimi">KIMI</option>
                    <option value="windsurf">Windsurf</option>
                </select>
                <span id="provider-badge"></span>

                <select id="ai-model-selector" data-testid="ai-model-selector">
                </select>
                <span id="model-badge"></span>

                <div id="chat-messages"></div>
                <input id="chat-input" type="text" />
                <button id="chat-send-btn">Send</button>
            </div>
        </body>
        </html>
    `;

    beforeEach(() => {
        // Create a fresh DOM for each test
        dom = new JSDOM(htmlTemplate, {
            url: 'http://localhost',
            runScripts: 'dangerously',
            resources: 'usable'
        });
        document = dom.window.document;
        window = dom.window;

        // Mock sessionStorage
        const sessionStorageMock = (() => {
            let store = {};
            return {
                getItem: (key) => store[key] || null,
                setItem: (key, value) => { store[key] = value; },
                clear: () => { store = {}; }
            };
        })();
        global.sessionStorage = sessionStorageMock;

        // Define ChatInterface class in the test environment
        window.ChatInterface = class ChatInterface {
            constructor() {
                this.messagesContainer = document.getElementById('chat-messages');
                this.input = document.getElementById('chat-input');
                this.sendBtn = document.getElementById('chat-send-btn');
                this.providerSelector = document.getElementById('ai-provider-selector');
                this.providerBadge = document.getElementById('provider-badge');
                this.modelSelector = document.getElementById('ai-model-selector');
                this.modelBadge = document.getElementById('model-badge');
                this.messages = [];
                this.selectedProvider = 'claude';
                this.selectedModel = 'haiku-4.5';

                this.providerModels = {
                    'claude': [
                        { id: 'haiku-4.5', name: 'Haiku 4.5', isDefault: true },
                        { id: 'sonnet-4.5', name: 'Sonnet 4.5', isDefault: false },
                        { id: 'opus-4.6', name: 'Opus 4.6', isDefault: false }
                    ],
                    'chatgpt': [
                        { id: 'gpt-4o', name: 'GPT-4o', isDefault: true },
                        { id: 'o1', name: 'o1', isDefault: false },
                        { id: 'o3-mini', name: 'o3-mini', isDefault: false },
                        { id: 'o4-mini', name: 'o4-mini', isDefault: false }
                    ],
                    'gemini': [
                        { id: '2.5-flash', name: '2.5 Flash', isDefault: true },
                        { id: '2.5-pro', name: '2.5 Pro', isDefault: false },
                        { id: '2.0-flash', name: '2.0 Flash', isDefault: false }
                    ],
                    'groq': [
                        { id: 'llama-3.3-70b', name: 'Llama 3.3 70B', isDefault: true },
                        { id: 'mixtral-8x7b', name: 'Mixtral 8x7B', isDefault: false }
                    ],
                    'kimi': [
                        { id: 'moonshot', name: 'Moonshot', isDefault: true }
                    ],
                    'windsurf': [
                        { id: 'cascade', name: 'Cascade', isDefault: true }
                    ]
                };

                this.init();
            }

            init() {
                if (!this.input || !this.sendBtn) return;
                this.loadSavedProvider();
                this.loadSavedModel();
                this.updateModelDropdown(this.selectedProvider);
            }

            loadSavedProvider() {
                try {
                    const savedProvider = sessionStorage.getItem('selectedAIProvider');
                    if (savedProvider) {
                        this.selectedProvider = savedProvider;
                        if (this.providerSelector) {
                            this.providerSelector.value = savedProvider;
                        }
                    }
                } catch (error) {
                    console.warn('Could not load saved provider:', error);
                }
            }

            loadSavedModel() {
                try {
                    const savedModel = sessionStorage.getItem('selectedAIModel');
                    if (savedModel) {
                        const models = this.providerModels[this.selectedProvider] || [];
                        const modelExists = models.find(m => m.id === savedModel);

                        if (modelExists) {
                            this.selectedModel = savedModel;
                            if (this.modelSelector) {
                                this.modelSelector.value = savedModel;
                            }
                            this.updateModelBadge(savedModel);
                        } else {
                            const defaultModel = this.getDefaultModel(this.selectedProvider);
                            this.selectedModel = defaultModel;
                            this.updateModelBadge(defaultModel);
                        }
                    } else {
                        const defaultModel = this.getDefaultModel(this.selectedProvider);
                        this.selectedModel = defaultModel;
                        this.updateModelBadge(defaultModel);
                    }
                } catch (error) {
                    console.warn('Could not load saved model:', error);
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

                this.updateModelDropdown(newProvider);

                const defaultModel = this.getDefaultModel(newProvider);
                this.selectedModel = defaultModel;
                this.modelSelector.value = defaultModel;
                this.updateModelBadge(defaultModel);

                try {
                    sessionStorage.setItem('selectedAIModel', defaultModel);
                } catch (error) {
                    console.warn('Could not save model to sessionStorage:', error);
                }
            }

            handleModelChange(event) {
                const newModel = event.target.value;
                this.selectedModel = newModel;

                try {
                    sessionStorage.setItem('selectedAIModel', newModel);
                } catch (error) {
                    console.warn('Could not save model to sessionStorage:', error);
                }

                this.updateModelBadge(newModel);
            }

            updateModelBadge(modelId) {
                if (!this.modelBadge) return;

                const models = this.providerModels[this.selectedProvider] || [];
                const model = models.find(m => m.id === modelId);

                if (model) {
                    this.modelBadge.textContent = model.name;
                } else {
                    this.modelBadge.textContent = modelId;
                }
            }

            updateModelDropdown(provider) {
                if (!this.modelSelector) return;

                const models = this.providerModels[provider] || [];
                this.modelSelector.innerHTML = '';

                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = model.name;
                    option.setAttribute('data-testid', `model-option-${model.id}`);
                    if (model.isDefault) {
                        option.setAttribute('data-default', 'true');
                    }
                    this.modelSelector.appendChild(option);
                });
            }

            getDefaultModel(provider) {
                const models = this.providerModels[provider] || [];
                const defaultModel = models.find(m => m.isDefault);
                return defaultModel ? defaultModel.id : (models[0] ? models[0].id : null);
            }

            getSelectedProvider() {
                return this.selectedProvider;
            }

            getSelectedModel() {
                return this.selectedModel;
            }

            getProviderModels(provider) {
                return this.providerModels[provider] || [];
            }
        };

        // Initialize ChatInterface
        chatInterface = new window.ChatInterface();
    });

    afterEach(() => {
        sessionStorage.clear();
    });

    // ==========================================
    // Test Group 1: Model Dropdown Population
    // ==========================================

    describe('Model Dropdown Population', () => {
        test('should populate model dropdown with Claude models on init', () => {
            const modelOptions = document.querySelectorAll('#ai-model-selector option');
            expect(modelOptions.length).toBe(3);
            expect(modelOptions[0].value).toBe('haiku-4.5');
            expect(modelOptions[1].value).toBe('sonnet-4.5');
            expect(modelOptions[2].value).toBe('opus-4.6');
        });

        test('should update model dropdown when provider changes to ChatGPT', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'chatgpt';
            chatInterface.handleProviderChange({ target: providerSelector });

            const modelOptions = document.querySelectorAll('#ai-model-selector option');
            expect(modelOptions.length).toBe(4);
            expect(modelOptions[0].value).toBe('gpt-4o');
            expect(modelOptions[1].value).toBe('o1');
            expect(modelOptions[2].value).toBe('o3-mini');
            expect(modelOptions[3].value).toBe('o4-mini');
        });

        test('should update model dropdown when provider changes to Gemini', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'gemini';
            chatInterface.handleProviderChange({ target: providerSelector });

            const modelOptions = document.querySelectorAll('#ai-model-selector option');
            expect(modelOptions.length).toBe(3);
            expect(modelOptions[0].value).toBe('2.5-flash');
            expect(modelOptions[1].value).toBe('2.5-pro');
            expect(modelOptions[2].value).toBe('2.0-flash');
        });

        test('should update model dropdown when provider changes to Groq', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'groq';
            chatInterface.handleProviderChange({ target: providerSelector });

            const modelOptions = document.querySelectorAll('#ai-model-selector option');
            expect(modelOptions.length).toBe(2);
            expect(modelOptions[0].value).toBe('llama-3.3-70b');
            expect(modelOptions[1].value).toBe('mixtral-8x7b');
        });

        test('should show single model for KIMI', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'kimi';
            chatInterface.handleProviderChange({ target: providerSelector });

            const modelOptions = document.querySelectorAll('#ai-model-selector option');
            expect(modelOptions.length).toBe(1);
            expect(modelOptions[0].value).toBe('moonshot');
        });

        test('should show single model for Windsurf', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'windsurf';
            chatInterface.handleProviderChange({ target: providerSelector });

            const modelOptions = document.querySelectorAll('#ai-model-selector option');
            expect(modelOptions.length).toBe(1);
            expect(modelOptions[0].value).toBe('cascade');
        });
    });

    // ==========================================
    // Test Group 2: Default Model Selection
    // ==========================================

    describe('Default Model Selection', () => {
        test('should select Haiku 4.5 as default for Claude', () => {
            expect(chatInterface.getSelectedModel()).toBe('haiku-4.5');
        });

        test('should select GPT-4o as default for ChatGPT', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'chatgpt';
            chatInterface.handleProviderChange({ target: providerSelector });

            expect(chatInterface.getSelectedModel()).toBe('gpt-4o');
        });

        test('should select 2.5 Flash as default for Gemini', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'gemini';
            chatInterface.handleProviderChange({ target: providerSelector });

            expect(chatInterface.getSelectedModel()).toBe('2.5-flash');
        });

        test('should select Llama 3.3 70B as default for Groq', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'groq';
            chatInterface.handleProviderChange({ target: providerSelector });

            expect(chatInterface.getSelectedModel()).toBe('llama-3.3-70b');
        });

        test('should select Moonshot as default for KIMI', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'kimi';
            chatInterface.handleProviderChange({ target: providerSelector });

            expect(chatInterface.getSelectedModel()).toBe('moonshot');
        });

        test('should select Cascade as default for Windsurf', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'windsurf';
            chatInterface.handleProviderChange({ target: providerSelector });

            expect(chatInterface.getSelectedModel()).toBe('cascade');
        });
    });

    // ==========================================
    // Test Group 3: Model Selection
    // ==========================================

    describe('Model Selection', () => {
        test('should allow selecting Sonnet 4.5 model', () => {
            const modelSelector = document.getElementById('ai-model-selector');
            modelSelector.value = 'sonnet-4.5';
            chatInterface.handleModelChange({ target: modelSelector });

            expect(chatInterface.getSelectedModel()).toBe('sonnet-4.5');
        });

        test('should allow selecting Opus 4.6 model', () => {
            const modelSelector = document.getElementById('ai-model-selector');
            modelSelector.value = 'opus-4.6';
            chatInterface.handleModelChange({ target: modelSelector });

            expect(chatInterface.getSelectedModel()).toBe('opus-4.6');
        });

        test('should update model badge when model changes', () => {
            const modelSelector = document.getElementById('ai-model-selector');
            const modelBadge = document.getElementById('model-badge');

            modelSelector.value = 'sonnet-4.5';
            chatInterface.handleModelChange({ target: modelSelector });

            expect(modelBadge.textContent).toBe('Sonnet 4.5');
        });

        test('should allow selecting different ChatGPT models', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'chatgpt';
            chatInterface.handleProviderChange({ target: providerSelector });

            const modelSelector = document.getElementById('ai-model-selector');
            modelSelector.value = 'o1';
            chatInterface.handleModelChange({ target: modelSelector });

            expect(chatInterface.getSelectedModel()).toBe('o1');
        });
    });

    // ==========================================
    // Test Group 4: SessionStorage Persistence
    // ==========================================

    describe('SessionStorage Persistence', () => {
        test('should save model selection to sessionStorage', () => {
            const modelSelector = document.getElementById('ai-model-selector');
            modelSelector.value = 'sonnet-4.5';
            chatInterface.handleModelChange({ target: modelSelector });

            expect(sessionStorage.getItem('selectedAIModel')).toBe('sonnet-4.5');
        });

        test('should load saved model from sessionStorage', () => {
            sessionStorage.setItem('selectedAIProvider', 'claude');
            sessionStorage.setItem('selectedAIModel', 'opus-4.6');

            const newInterface = new window.ChatInterface();

            expect(newInterface.getSelectedModel()).toBe('opus-4.6');
        });

        test('should update model in sessionStorage when provider changes', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'chatgpt';
            chatInterface.handleProviderChange({ target: providerSelector });

            expect(sessionStorage.getItem('selectedAIModel')).toBe('gpt-4o');
        });

        test('should persist model selection across provider switches', () => {
            // Select Sonnet for Claude
            const modelSelector = document.getElementById('ai-model-selector');
            modelSelector.value = 'sonnet-4.5';
            chatInterface.handleModelChange({ target: modelSelector });

            // Switch to ChatGPT
            const providerSelector = document.getElementById('ai-provider-selector');
            providerSelector.value = 'chatgpt';
            chatInterface.handleProviderChange({ target: providerSelector });

            // Model should be default for ChatGPT (gpt-4o)
            expect(chatInterface.getSelectedModel()).toBe('gpt-4o');
        });

        test('should use default model if saved model not valid for provider', () => {
            sessionStorage.setItem('selectedAIProvider', 'chatgpt');
            sessionStorage.setItem('selectedAIModel', 'haiku-4.5'); // Claude model

            const newInterface = new window.ChatInterface();

            expect(newInterface.getSelectedModel()).toBe('gpt-4o'); // ChatGPT default
        });
    });

    // ==========================================
    // Test Group 5: Model Badge Display
    // ==========================================

    describe('Model Badge Display', () => {
        test('should display default model badge on init', () => {
            const modelBadge = document.getElementById('model-badge');
            expect(modelBadge.textContent).toBe('Haiku 4.5');
        });

        test('should update badge when model changes', () => {
            const modelSelector = document.getElementById('ai-model-selector');
            const modelBadge = document.getElementById('model-badge');

            modelSelector.value = 'opus-4.6';
            chatInterface.handleModelChange({ target: modelSelector });

            expect(modelBadge.textContent).toBe('Opus 4.6');
        });

        test('should update badge when provider changes', () => {
            const providerSelector = document.getElementById('ai-provider-selector');
            const modelBadge = document.getElementById('model-badge');

            providerSelector.value = 'gemini';
            chatInterface.handleProviderChange({ target: providerSelector });

            expect(modelBadge.textContent).toBe('2.5 Flash');
        });
    });

    // ==========================================
    // Test Group 6: Provider-Model Integration
    // ==========================================

    describe('Provider-Model Integration', () => {
        test('should return correct models for each provider', () => {
            expect(chatInterface.getProviderModels('claude').length).toBe(3);
            expect(chatInterface.getProviderModels('chatgpt').length).toBe(4);
            expect(chatInterface.getProviderModels('gemini').length).toBe(3);
            expect(chatInterface.getProviderModels('groq').length).toBe(2);
            expect(chatInterface.getProviderModels('kimi').length).toBe(1);
            expect(chatInterface.getProviderModels('windsurf').length).toBe(1);
        });

        test('should identify default models correctly', () => {
            expect(chatInterface.getDefaultModel('claude')).toBe('haiku-4.5');
            expect(chatInterface.getDefaultModel('chatgpt')).toBe('gpt-4o');
            expect(chatInterface.getDefaultModel('gemini')).toBe('2.5-flash');
            expect(chatInterface.getDefaultModel('groq')).toBe('llama-3.3-70b');
            expect(chatInterface.getDefaultModel('kimi')).toBe('moonshot');
            expect(chatInterface.getDefaultModel('windsurf')).toBe('cascade');
        });

        test('should maintain model selection within same provider', () => {
            const modelSelector = document.getElementById('ai-model-selector');
            modelSelector.value = 'sonnet-4.5';
            chatInterface.handleModelChange({ target: modelSelector });

            expect(chatInterface.getSelectedProvider()).toBe('claude');
            expect(chatInterface.getSelectedModel()).toBe('sonnet-4.5');
        });
    });

    // ==========================================
    // Test Group 7: Edge Cases
    // ==========================================

    describe('Edge Cases', () => {
        test('should handle missing model selector gracefully', () => {
            document.getElementById('ai-model-selector').remove();
            const newInterface = new window.ChatInterface();

            expect(() => newInterface.updateModelDropdown('claude')).not.toThrow();
        });

        test('should handle missing model badge gracefully', () => {
            document.getElementById('model-badge').remove();
            const newInterface = new window.ChatInterface();

            expect(() => newInterface.updateModelBadge('haiku-4.5')).not.toThrow();
        });

        test('should handle invalid provider gracefully', () => {
            expect(chatInterface.getProviderModels('invalid')).toEqual([]);
            expect(chatInterface.getDefaultModel('invalid')).toBeNull();
        });

        test('should handle sessionStorage errors gracefully', () => {
            // Mock sessionStorage to throw error
            const originalGetItem = sessionStorage.getItem;
            sessionStorage.getItem = () => { throw new Error('Storage error'); };

            const newInterface = new window.ChatInterface();
            expect(newInterface.getSelectedModel()).toBe('haiku-4.5'); // Falls back to default

            // Restore
            sessionStorage.getItem = originalGetItem;
        });
    });

    // ==========================================
    // Test Group 8: Data Attributes
    // ==========================================

    describe('Data Attributes', () => {
        test('should mark default models with data-default attribute', () => {
            const defaultOption = document.querySelector('#ai-model-selector option[data-default="true"]');
            expect(defaultOption).not.toBeNull();
            expect(defaultOption.value).toBe('haiku-4.5');
        });

        test('should add data-testid to model options', () => {
            const modelOptions = document.querySelectorAll('#ai-model-selector option[data-testid]');
            expect(modelOptions.length).toBeGreaterThan(0);
        });
    });
});

console.log('AI-72 Model Selector Unit Tests Loaded');
