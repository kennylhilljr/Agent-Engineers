/**
 * Chat Interface Tests
 * Comprehensive test suite for AI-68: Chat Interface
 */

describe('Chat Interface - AI-68', () => {
    let chatInterface;
    let messagesContainer;
    let input;
    let sendBtn;

    beforeEach(() => {
        // Setup DOM elements
        document.body.innerHTML = `
            <div id="chat-container" class="chat-container">
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
                            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
                            </svg>
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
                this.messages = [];
                this.init();
            }

            init() {
                if (!this.input || !this.sendBtn) return;
                this.sendBtn.addEventListener('click', () => this.sendMessage());
                this.input.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        this.sendMessage();
                    }
                });
            }

            sendMessage() {
                const text = this.input.value.trim();
                if (!text) return;
                this.addMessage(text, 'user');
                this.input.value = '';
                this.showLoadingIndicator();
                setTimeout(() => {
                    this.removeLoadingIndicator();
                    this.addMessage(this.generateAIResponse(text), 'ai');
                }, 800);
            }

            addMessage(text, sender) {
                const message = {
                    id: Date.now(),
                    text,
                    sender,
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

            generateAIResponse(userMessage) {
                const lower = userMessage.toLowerCase();
                if (lower.includes('status') || lower.includes('how')) {
                    return 'Your agents are running smoothly. All systems are operational with 99.2% uptime.';
                }
                if (lower.includes('metric') || lower.includes('performance')) {
                    return 'Current metrics show strong performance: 94% success rate, avg response time 245ms.';
                }
                if (lower.includes('error') || lower.includes('issue') || lower.includes('problem')) {
                    return 'No critical errors detected. All monitoring systems are reporting normal status.';
                }
                if (lower.includes('cost') || lower.includes('usage') || lower.includes('token')) {
                    return 'Token usage is at 42% of daily allocation. Cost trending 8% below budget.';
                }
                if (lower.includes('hello') || lower.includes('hi') || lower.includes('hey')) {
                    return 'Hello! I\'m here to help you with any questions about your agent dashboard.';
                }
                return 'I understand. Based on your agent dashboard, everything is performing within expected parameters. Is there anything specific you\'d like to know?';
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
        messagesContainer = document.getElementById('chat-messages');
        input = document.getElementById('chat-input');
        sendBtn = document.getElementById('chat-send-btn');
    });

    describe('Chat Interface Initialization', () => {
        test('should initialize with empty messages array', () => {
            expect(chatInterface.messages).toEqual([]);
        });

        test('should have chat container visible', () => {
            const container = document.getElementById('chat-container');
            expect(container).toBeInTheDocument();
            expect(container).toHaveClass('chat-container');
        });

        test('should display welcome message on load', () => {
            const welcome = messagesContainer.querySelector('.chat-welcome');
            expect(welcome).toBeInTheDocument();
            expect(welcome).toHaveTextContent('Welcome to the Agent Dashboard Chat');
        });

        test('should have input field with correct placeholder', () => {
            expect(input).toHaveAttribute('placeholder', "Type a message... (e.g., 'What's my status?')");
        });

        test('should have send button with aria-label', () => {
            expect(sendBtn).toHaveAttribute('aria-label', 'Send message');
        });
    });

    describe('Message Submission', () => {
        test('should add user message when send button is clicked', (done) => {
            input.value = 'Hello, what\'s my status?';
            sendBtn.click();

            setTimeout(() => {
                const userMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-user"]');
                expect(userMessages.length).toBe(1);
                expect(userMessages[0]).toHaveTextContent('Hello, what\'s my status?');
                done();
            }, 100);
        });

        test('should clear input field after sending message', () => {
            input.value = 'Test message';
            sendBtn.click();
            expect(input.value).toBe('');
        });

        test('should not send empty messages', () => {
            input.value = '   ';
            sendBtn.click();
            expect(chatInterface.messages.length).toBe(0);
        });

        test('should send message on Enter key press', (done) => {
            input.value = 'Test message';
            const event = new KeyboardEvent('keypress', { key: 'Enter' });
            input.dispatchEvent(event);

            setTimeout(() => {
                const userMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-user"]');
                expect(userMessages.length).toBe(1);
                done();
            }, 100);
        });

        test('should not send message on Shift+Enter', () => {
            input.value = 'Test message';
            const event = new KeyboardEvent('keypress', { key: 'Enter', shiftKey: true });
            input.dispatchEvent(event);
            expect(input.value).toBe('Test message');
        });
    });

    describe('Message Rendering - User vs AI', () => {
        test('should render user message with correct styling', (done) => {
            input.value = 'User message';
            sendBtn.click();

            setTimeout(() => {
                const userMessage = messagesContainer.querySelector('[data-testid="chat-message-user"]');
                expect(userMessage).toHaveClass('chat-message', 'user');
                expect(userMessage).toHaveTextContent('User message');
                done();
            }, 100);
        });

        test('should render AI message with correct styling', (done) => {
            input.value = 'Hello';
            sendBtn.click();

            setTimeout(() => {
                const aiMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-ai"]');
                expect(aiMessages.length).toBeGreaterThan(0);
                const aiMessage = aiMessages[0];
                expect(aiMessage).toHaveClass('chat-message', 'ai');
                done();
            }, 1000);
        });

        test('should display distinct visual styles for user and AI messages', (done) => {
            input.value = 'Test message';
            sendBtn.click();

            setTimeout(() => {
                const userDiv = messagesContainer.querySelector('[data-testid="chat-message-user"]');
                const aiDiv = messagesContainer.querySelector('[data-testid="chat-message-ai"]');

                expect(userDiv).toBeTruthy();
                expect(aiDiv).toBeTruthy();
                expect(userDiv.className).not.toBe(aiDiv.className);
                done();
            }, 1000);
        });

        test('should remove welcome message on first message', (done) => {
            const welcomeInitial = messagesContainer.querySelector('.chat-welcome');
            expect(welcomeInitial).toBeInTheDocument();

            input.value = 'First message';
            sendBtn.click();

            setTimeout(() => {
                const welcomeAfter = messagesContainer.querySelector('.chat-welcome');
                expect(welcomeAfter).not.toBeInTheDocument();
                done();
            }, 100);
        });
    });

    describe('Timestamp Display', () => {
        test('should display timestamp on user messages', (done) => {
            input.value = 'Message with timestamp';
            sendBtn.click();

            setTimeout(() => {
                const messageDiv = messagesContainer.querySelector('[data-testid="chat-message-user"]');
                const timestamp = messageDiv.querySelector('.chat-timestamp');
                expect(timestamp).toBeInTheDocument();
                expect(timestamp.textContent).toMatch(/\d{2}:\d{2}/);
                done();
            }, 100);
        });

        test('should display timestamp on AI messages', (done) => {
            input.value = 'Hello';
            sendBtn.click();

            setTimeout(() => {
                const aiMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-ai"]');
                const aiMessage = aiMessages[0];
                const timestamp = aiMessage.querySelector('.chat-timestamp');
                expect(timestamp).toBeInTheDocument();
                expect(timestamp.textContent).toMatch(/\d{2}:\d{2}/);
                done();
            }, 1000);
        });

        test('should display valid time format', (done) => {
            input.value = 'Test';
            sendBtn.click();

            setTimeout(() => {
                const timestamps = messagesContainer.querySelectorAll('.chat-timestamp');
                timestamps.forEach(ts => {
                    const timeText = ts.textContent.trim();
                    expect(timeText).toMatch(/^\d{1,2}:\d{2}\s*(AM|PM|a\.m\.|p\.m\.)?$/i);
                });
                done();
            }, 100);
        });
    });

    describe('Scrollable Conversation History', () => {
        test('should auto-scroll to latest message', (done) => {
            input.value = 'Message 1';
            sendBtn.click();

            setTimeout(() => {
                const scrollTop = messagesContainer.scrollTop;
                const scrollHeight = messagesContainer.scrollHeight;
                const clientHeight = messagesContainer.clientHeight;
                expect(scrollTop + clientHeight).toBeGreaterThanOrEqual(scrollHeight - 10);
                done();
            }, 100);
        });

        test('should display multiple messages in conversation', (done) => {
            input.value = 'First message';
            sendBtn.click();

            setTimeout(() => {
                input.value = 'Second message';
                sendBtn.click();

                setTimeout(() => {
                    const messages = messagesContainer.querySelectorAll('[data-testid^="chat-message-"]');
                    expect(messages.length).toBeGreaterThanOrEqual(2);
                    done();
                }, 100);
            }, 900);
        });

        test('should maintain message order', (done) => {
            input.value = 'First';
            sendBtn.click();

            setTimeout(() => {
                input.value = 'Second';
                sendBtn.click();

                setTimeout(() => {
                    const messages = chatInterface.getMessages();
                    expect(messages[0].text).toBe('First');
                    expect(messages[1].text).toBe('Second');
                    done();
                }, 100);
            }, 900);
        });

        test('should allow scrolling through conversation history', (done) => {
            // Add multiple messages
            input.value = 'Message 1';
            sendBtn.click();

            setTimeout(() => {
                input.value = 'Message 2';
                sendBtn.click();

                setTimeout(() => {
                    const messageCount = messagesContainer.querySelectorAll('[data-testid^="chat-message-"]').length;
                    expect(messageCount).toBeGreaterThan(0);
                    expect(messagesContainer.scrollHeight).toBeGreaterThan(messagesContainer.clientHeight);
                    done();
                }, 900);
            }, 900);
        });
    });

    describe('AI Response Generation', () => {
        test('should generate status-related response', (done) => {
            input.value = 'What\'s my status?';
            sendBtn.click();

            setTimeout(() => {
                const aiMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-ai"]');
                expect(aiMessages.length).toBeGreaterThan(0);
                expect(aiMessages[0]).toHaveTextContent('99.2% uptime');
                done();
            }, 1000);
        });

        test('should generate metric-related response', (done) => {
            input.value = 'Show me the metrics';
            sendBtn.click();

            setTimeout(() => {
                const aiMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-ai"]');
                expect(aiMessages[0]).toHaveTextContent('94% success rate');
                done();
            }, 1000);
        });

        test('should generate cost-related response', (done) => {
            input.value = 'How is my token usage?';
            sendBtn.click();

            setTimeout(() => {
                const aiMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-ai"]');
                expect(aiMessages[0]).toHaveTextContent('42% of daily allocation');
                done();
            }, 1000);
        });

        test('should generate greeting response', (done) => {
            input.value = 'Hello there!';
            sendBtn.click();

            setTimeout(() => {
                const aiMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-ai"]');
                expect(aiMessages[0]).toHaveTextContent('Hello!');
                done();
            }, 1000);
        });

        test('should generate default response for unknown queries', (done) => {
            input.value = 'Random question xyz';
            sendBtn.click();

            setTimeout(() => {
                const aiMessages = messagesContainer.querySelectorAll('[data-testid="chat-message-ai"]');
                expect(aiMessages[0]).toHaveTextContent('performing within expected parameters');
                done();
            }, 1000);
        });
    });

    describe('Loading Indicator', () => {
        test('should show loading indicator while processing', (done) => {
            input.value = 'Test';
            sendBtn.click();

            const loadingIndicator = document.getElementById('chat-loading');
            expect(loadingIndicator).toBeInTheDocument();
            expect(loadingIndicator).toHaveAttribute('data-testid', 'chat-loading-indicator');

            setTimeout(() => {
                done();
            }, 100);
        });

        test('should hide loading indicator after response', (done) => {
            input.value = 'Test';
            sendBtn.click();

            setTimeout(() => {
                const loadingIndicator = document.getElementById('chat-loading');
                expect(loadingIndicator).not.toBeInTheDocument();
                done();
            }, 900);
        });
    });

    describe('HTML Escaping and Security', () => {
        test('should escape HTML special characters in user messages', (done) => {
            input.value = '<script>alert("xss")</script>';
            sendBtn.click();

            setTimeout(() => {
                const userMessage = messagesContainer.querySelector('[data-testid="chat-message-user"]');
                const content = userMessage.querySelector('.chat-message-content');
                expect(content.textContent).toContain('<script>');
                expect(content.innerHTML).not.toContain('<script>');
                done();
            }, 100);
        });

        test('should escape HTML in AI responses', (done) => {
            // Manually add a message with HTML
            chatInterface.addMessage('<div>HTML content</div>', 'ai');

            setTimeout(() => {
                const aiMessage = messagesContainer.querySelector('[data-testid="chat-message-ai"]');
                const content = aiMessage.querySelector('.chat-message-content');
                expect(content.textContent).toContain('<div>');
                expect(content.innerHTML).not.toContain('<div>HTML content</div>');
                done();
            }, 100);
        });
    });

    describe('Utility Methods', () => {
        test('should retrieve all messages', () => {
            chatInterface.addMessage('Test message', 'user');
            const messages = chatInterface.getMessages();
            expect(messages.length).toBe(1);
            expect(messages[0].text).toBe('Test message');
        });

        test('should clear all messages', () => {
            chatInterface.addMessage('Message 1', 'user');
            chatInterface.addMessage('Message 2', 'ai');
            chatInterface.clearMessages();
            expect(chatInterface.getMessages().length).toBe(0);
        });

        test('should restore welcome message after clear', () => {
            chatInterface.addMessage('Message', 'user');
            chatInterface.clearMessages();
            const welcome = messagesContainer.querySelector('.chat-welcome');
            expect(welcome).toBeInTheDocument();
        });
    });

    describe('Edge Cases', () => {
        test('should handle very long messages', (done) => {
            const longMessage = 'A'.repeat(500);
            input.value = longMessage;
            sendBtn.click();

            setTimeout(() => {
                const userMessage = messagesContainer.querySelector('[data-testid="chat-message-user"]');
                expect(userMessage).toHaveTextContent(longMessage);
                done();
            }, 100);
        });

        test('should handle special characters in messages', (done) => {
            input.value = 'Test with special chars: !@#$%^&*()_+-=[]{}|;:,.<>?/';
            sendBtn.click();

            setTimeout(() => {
                const userMessage = messagesContainer.querySelector('[data-testid="chat-message-user"]');
                expect(userMessage).toHaveTextContent('!@#$%^&*()');
                done();
            }, 100);
        });

        test('should handle rapid message submissions', (done) => {
            input.value = 'Message 1';
            sendBtn.click();
            input.value = 'Message 2';
            sendBtn.click();
            input.value = 'Message 3';
            sendBtn.click();

            setTimeout(() => {
                const messages = chatInterface.getMessages();
                expect(messages.length).toBeGreaterThanOrEqual(3);
                done();
            }, 100);
        });

        test('should preserve message data (id, timestamp, sender)', (done) => {
            input.value = 'Test message';
            sendBtn.click();

            setTimeout(() => {
                const message = chatInterface.getMessages()[0];
                expect(message).toHaveProperty('id');
                expect(message).toHaveProperty('text');
                expect(message).toHaveProperty('sender');
                expect(message).toHaveProperty('timestamp');
                expect(message.sender).toBe('user');
                done();
            }, 100);
        });
    });
});
