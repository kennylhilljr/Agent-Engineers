/**
 * Chat Interface Class
 * Handles chat message rendering, code block parsing, and syntax highlighting
 */

class ChatMessageHistory {
    constructor(storageKey = 'chat_message_history_session') {
        this.storageKey = storageKey;
        this.maxStorageSize = 10 * 1024 * 1024; // 10MB limit
    }

    saveMessages(messages) {
        try {
            const data = JSON.stringify({
                version: '1.0',
                timestamp: new Date().toISOString(),
                messages: messages
            });

            if (data.length > this.maxStorageSize) {
                console.warn('Storage size exceeded, clearing old messages');
                // Keep only the last 50 messages if exceeds limit
                const trimmedMessages = messages.slice(-50);
                const trimmedData = JSON.stringify({
                    version: '1.0',
                    timestamp: new Date().toISOString(),
                    messages: trimmedMessages
                });
                localStorage.setItem(this.storageKey, trimmedData);
                return trimmedMessages;
            }

            localStorage.setItem(this.storageKey, data);
            return messages;
        } catch (error) {
            console.error('Failed to save messages to localStorage:', error);
            // Fallback: clear and retry with smaller dataset
            try {
                localStorage.removeItem(this.storageKey);
                const lastMessages = messages.slice(-25);
                localStorage.setItem(this.storageKey, JSON.stringify({
                    version: '1.0',
                    timestamp: new Date().toISOString(),
                    messages: lastMessages
                }));
            } catch (retryError) {
                console.error('Failed to save even reduced message set:', retryError);
            }
        }
    }

    loadMessages() {
        try {
            const data = localStorage.getItem(this.storageKey);
            if (!data) return [];

            const parsed = JSON.parse(data);
            if (!parsed.messages || !Array.isArray(parsed.messages)) {
                return [];
            }

            // Restore timestamp as Date object
            return parsed.messages.map(msg => ({
                ...msg,
                timestamp: new Date(msg.timestamp)
            }));
        } catch (error) {
            console.error('Failed to load messages from localStorage:', error);
            return [];
        }
    }

    clearMessages() {
        try {
            localStorage.removeItem(this.storageKey);
        } catch (error) {
            console.error('Failed to clear messages from localStorage:', error);
        }
    }

    getStorageInfo() {
        try {
            const data = localStorage.getItem(this.storageKey);
            if (!data) return { isEmpty: true, messageCount: 0, sizeBytes: 0 };

            const parsed = JSON.parse(data);
            return {
                isEmpty: false,
                messageCount: (parsed.messages || []).length,
                sizeBytes: new Blob([data]).size,
                lastUpdated: parsed.timestamp
            };
        } catch (error) {
            return { isEmpty: true, messageCount: 0, sizeBytes: 0, error: error.message };
        }
    }
}

class ChatInterface {
    constructor() {
        this.messagesContainer = document.getElementById('chat-messages');
        this.input = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('chat-send-btn');
        this.messages = [];
        this.history = new ChatMessageHistory();

        this.init();
        this.loadPersistedMessages();
    }

    init() {
        if (!this.input || !this.sendBtn) {
            console.warn('Chat interface elements not found');
            return;
        }

        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }

    loadPersistedMessages() {
        const persistedMessages = this.history.loadMessages();
        if (persistedMessages.length > 0) {
            this.messages = persistedMessages;
            // Clear welcome message and render persisted messages
            const welcome = this.messagesContainer.querySelector('.chat-welcome');
            if (welcome) {
                welcome.remove();
            }
            // Render all persisted messages
            persistedMessages.forEach(message => {
                this.renderMessage(message);
            });
        }
    }

    sendMessage() {
        const text = this.input.value.trim();
        if (!text) return;

        // Add user message
        this.addMessage(text, 'user');
        this.input.value = '';

        // Get provider selection from the dropdown (AI-262 fix)
        const providerSelector = document.getElementById('ai-provider-selector');
        const provider = providerSelector ? providerSelector.value : 'claude';

        // Call the real /api/chat SSE endpoint (AI-262 fix: replace fake generateAIResponse)
        this.showLoadingIndicator();
        this._streamChatResponse(text, provider);
    }

    async _streamChatResponse(text, provider) {
        // Build conversation history for context
        const conversationHistory = this.messages
            .filter(m => m.sender !== 'system')
            .slice(-10)
            .map(m => ({ role: m.sender === 'user' ? 'user' : 'assistant', content: m.text }));

        let aiText = '';
        let aiBubble = null;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    provider: provider,
                    conversation_history: conversationHistory
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.removeLoadingIndicator();

            const contentType = response.headers.get('content-type') || '';

            if (contentType.includes('text/event-stream')) {
                // Parse SSE stream
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // keep incomplete line

                    for (const line of lines) {
                        if (!line.startsWith('data: ')) continue;
                        const rawData = line.slice(6).trim();
                        if (!rawData || rawData === '[DONE]') continue;

                        let chunk;
                        try { chunk = JSON.parse(rawData); } catch { continue; }

                        if (chunk.type === 'text' && chunk.content) {
                            aiText += chunk.content;
                            if (!aiBubble) {
                                // Create the AI message bubble for streaming
                                aiBubble = this._createStreamingBubble();
                            }
                            this._updateStreamingBubble(aiBubble, aiText);
                            this.scrollToBottom();
                        } else if (chunk.type === 'done') {
                            break;
                        } else if (chunk.type === 'error') {
                            throw new Error(chunk.message || 'Stream error');
                        }
                    }
                }
            } else {
                // JSON fallback response
                const json = await response.json();
                aiText = json.response || json.message || JSON.stringify(json);
            }

            // Save final AI message to history
            if (aiText) {
                const message = {
                    id: Date.now(),
                    text: aiText,
                    sender: 'ai',
                    timestamp: new Date(),
                    type: 'message'
                };
                this.messages.push(message);
                this.history.saveMessages(this.messages);
                if (!aiBubble) {
                    // Non-streaming: render via normal path
                    this.renderMessage(message);
                }
            } else {
                this.addMessage(
                    'Configure an API key in Settings to get real AI responses.',
                    'ai'
                );
            }

        } catch (err) {
            console.error('[ChatInterface] _streamChatResponse error:', err);
            this.removeLoadingIndicator();
            this.addMessage(
                `Unable to reach AI provider: ${err.message}. Configure an API key in Settings.`,
                'ai'
            );
        }

        this.scrollToBottom();
    }

    _createStreamingBubble() {
        const div = document.createElement('div');
        div.className = 'chat-message ai';
        div.setAttribute('data-testid', 'chat-message-ai');

        const content = document.createElement('div');
        content.className = 'chat-message-content';
        content.setAttribute('data-streaming', 'true');

        div.appendChild(content);
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
        return { div, content };
    }

    _updateStreamingBubble(bubble, text) {
        bubble.content.textContent = text;
    }

    addMessage(text, sender, type = 'message') {
        const message = {
            id: Date.now(),
            text,
            sender,
            timestamp: new Date(),
            type: type // 'message', 'system', 'error', etc.
        };

        this.messages.push(message);
        this.history.saveMessages(this.messages);
        this.renderMessage(message);
        this.scrollToBottom();
    }

    renderMessage(message) {
        // Remove welcome message on first message
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

        // Parse message for code blocks and render appropriately
        const messageContent = this.parseMessageContent(message.text);

        let contentHtml = '';
        messageContent.forEach(part => {
            if (part.type === 'text') {
                contentHtml += `<div class="chat-message-content">${this.escapeHtml(part.content)}</div>`;
            } else if (part.type === 'code') {
                contentHtml += this.renderCodeBlock(part.content, part.language, part.filePath);
            } else if (part.type === 'diff') {
                contentHtml += this.renderDiffBlock(part.content, part.language, part.filePath);
            }
        });

        content.innerHTML = contentHtml + `<div class="chat-timestamp">${timeStr}</div>`;

        div.appendChild(content);
        this.messagesContainer.appendChild(div);

        // Apply syntax highlighting to code blocks
        if (message.sender === 'ai') {
            setTimeout(() => {
                div.querySelectorAll('code').forEach(codeBlock => {
                    if (codeBlock.className && typeof hljs !== 'undefined') {
                        hljs.highlightElement(codeBlock);
                    }
                });
            }, 0);
        }
    }

    parseMessageContent(text) {
        const parts = [];
        let remaining = text;

        // Pattern to match code blocks with optional language and filepath
        const codeBlockPattern = /```(?:(\w+))?\s*(?:@(\S+))?\n([\s\S]*?)```/g;
        const diffPattern = /```diff\s*(?:@(\S+))?\n([\s\S]*?)```/g;

        let lastIndex = 0;
        let match;

        // Check for diff blocks first
        while ((match = diffPattern.exec(text)) !== null) {
            if (match.index > lastIndex) {
                parts.push({
                    type: 'text',
                    content: text.substring(lastIndex, match.index)
                });
            }

            parts.push({
                type: 'diff',
                content: match[2],
                filePath: match[1] || null,
                language: 'diff'
            });

            lastIndex = diffPattern.lastIndex;
        }

        // Check for regular code blocks
        codeBlockPattern.lastIndex = 0;
        while ((match = codeBlockPattern.exec(text)) !== null) {
            // Skip if already matched as diff
            if (match.index >= lastIndex && text.substring(match.index, match.index + 10).includes('diff')) {
                continue;
            }

            if (match.index > lastIndex) {
                parts.push({
                    type: 'text',
                    content: text.substring(lastIndex, match.index)
                });
            }

            parts.push({
                type: 'code',
                content: match[3],
                language: match[1] || 'plaintext',
                filePath: match[2] || null
            });

            lastIndex = codeBlockPattern.lastIndex;
        }

        if (lastIndex < text.length) {
            parts.push({
                type: 'text',
                content: text.substring(lastIndex)
            });
        }

        return parts.length > 0 ? parts : [{type: 'text', content: text}];
    }

    renderCodeBlock(code, language, filePath) {
        const safeLanguage = this.escapeHtml(language || 'plaintext');
        const displayPath = filePath ? `<div class="code-block-filepath">${this.escapeHtml(filePath)}</div>` : '';
        const blockId = `code-block-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

        return `
            <div class="code-block-wrapper" style="max-width: 90%; margin: 8px 0;">
                <div class="code-block-header">
                    <span class="code-block-language">${safeLanguage}</span>
                    ${displayPath}
                    <div class="code-block-actions">
                        <button class="copy-btn" onclick="window.chatInterface.copyToClipboard('${blockId}')" data-testid="copy-code-btn">
                            Copy
                        </button>
                    </div>
                </div>
                <div class="code-block" id="${blockId}">
                    <code class="language-${language || 'plaintext'} hljs">${this.escapeHtml(code)}</code>
                </div>
            </div>
        `;
    }

    renderDiffBlock(code, language, filePath) {
        const displayPath = filePath ? `<div class="code-block-filepath">${this.escapeHtml(filePath)}</div>` : '';
        const blockId = `diff-block-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

        // Parse diff lines and apply styling
        const lines = code.split('\n');
        let diffHtml = '';

        lines.forEach(line => {
            if (line.startsWith('+') && !line.startsWith('+++')) {
                diffHtml += `<div class="code-line added"><span class="diff-indicator">+</span><code>${this.escapeHtml(line.substring(1))}</code></div>`;
            } else if (line.startsWith('-') && !line.startsWith('---')) {
                diffHtml += `<div class="code-line deleted"><span class="diff-indicator">-</span><code>${this.escapeHtml(line.substring(1))}</code></div>`;
            } else {
                diffHtml += `<div class="code-line neutral"><span class="diff-indicator"> </span><code>${this.escapeHtml(line)}</code></div>`;
            }
        });

        return `
            <div class="code-block-wrapper code-block-diff" style="max-width: 90%; margin: 8px 0;">
                <div class="code-block-header">
                    <span class="code-block-language">DIFF</span>
                    ${displayPath}
                    <div class="code-block-actions">
                        <button class="copy-btn" onclick="window.chatInterface.copyToClipboard('${blockId}')" data-testid="copy-diff-btn">
                            Copy
                        </button>
                    </div>
                </div>
                <div class="code-block" id="${blockId}" style="padding: 0; overflow: auto;">
                    ${diffHtml}
                </div>
            </div>
        `;
    }

    copyToClipboard(blockId) {
        const element = document.getElementById(blockId);
        if (!element) return;

        let text = '';
        if (element.querySelector('code')) {
            const codeElement = element.querySelector('code');
            text = codeElement.textContent || codeElement.innerText;
        } else {
            // For diff blocks
            const lines = element.querySelectorAll('.code-line');
            text = Array.from(lines)
                .map(line => {
                    const indicator = line.querySelector('.diff-indicator').textContent;
                    const code = line.querySelector('code').textContent;
                    return indicator + code;
                })
                .join('\n');
        }

        navigator.clipboard.writeText(text).then(() => {
            // Find the copy button and give feedback
            const button = element.parentElement.querySelector('.copy-btn');
            if (button) {
                const originalText = button.textContent;
                button.textContent = 'Copied!';
                button.classList.add('copied');
                setTimeout(() => {
                    button.textContent = originalText;
                    button.classList.remove('copied');
                }, 2000);
            }
        }).catch(err => {
            console.error('Failed to copy to clipboard:', err);
        });
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
        if (loading) {
            loading.remove();
        }
    }

    generateAIResponse(userMessage) {
        // Simple response generation based on keywords
        const lower = userMessage.toLowerCase();

        if (lower.includes('python') || lower.includes('code') && lower.includes('python')) {
            return 'Here\'s a Python example:\n\n```python\n# Example Python function\ndef calculate_metrics(data):\n    """Calculate performance metrics from data."""\n    total = sum(data)\n    average = total / len(data)\n    return {\n        "total": total,\n        "average": average,\n        "count": len(data)\n    }\n\n# Usage\nmetrics = calculate_metrics([10, 20, 30, 40, 50])\nprint(metrics)\n```\n\nThis function processes a list of values and returns key statistics.';
        }

        if (lower.includes('javascript') || lower.includes('js') || (lower.includes('code') && lower.includes('javascript'))) {
            return 'Here\'s a JavaScript example:\n\n```javascript\n// Example JavaScript function\nfunction initializeChat() {\n    const chatInterface = new ChatInterface();\n    console.log("Chat initialized");\n    return chatInterface;\n}\n\n// With event listeners\nconst chat = initializeChat();\nchat.on("message", (msg) => {\n    console.log("New message:", msg);\n});\n```\n\nThis initializes the chat interface with event handling.';
        }

        if (lower.includes('html') || lower.includes('css')) {
            return 'Here\'s an HTML/CSS example:\n\n```html\n<div class="chat-container">\n    <div class="chat-header">\n        <h2>Agent Dashboard</h2>\n    </div>\n    <div class="chat-messages">\n        <!-- Messages will appear here -->\n    </div>\n</div>\n```\n\n```css\n.chat-container {\n    display: flex;\n    flex-direction: column;\n    height: 500px;\n    gap: 16px;\n}\n```';
        }

        if ((lower.includes('change') || lower.includes('diff') || lower.includes('modify')) && lower.includes('code')) {
            return 'Here\'s a code change example:\n\n```diff\n@example.py\n- def old_function():\n-     return "old value"\n+ def new_function():\n+     return "new value"\n+     # Added new functionality\n```\n\nThe diff shows additions (green +) and deletions (red -).';
        }

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
        this.history.clearMessages();
        this.messagesContainer.innerHTML = `
            <div class="chat-welcome">
                <p>Welcome to the Agent Dashboard Chat. Ask me anything about your agent status, metrics, or general questions!</p>
            </div>
        `;
    }

    getStorageInfo() {
        return this.history.getStorageInfo();
    }
}

// Export for Node.js/Jest testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChatInterface, ChatMessageHistory };
}
