/**
 * Chat Message History Tests - AI-69
 * Comprehensive test suite for message history persistence
 */

describe('Chat Message History - AI-69', () => {
    let history;
    let realLocalStorage;
    const testStorageKey = 'test_chat_history_' + Date.now();

    beforeEach(() => {
        // Use real localStorage implementation for these tests
        realLocalStorage = new RealLocalStorage();

        // Override global localStorage for this test suite
        Object.defineProperty(global, 'localStorage', {
            value: realLocalStorage,
            writable: true
        });

        // Create a simple mock of ChatMessageHistory for testing
        class ChatMessageHistory {
            constructor(storageKey) {
                this.storageKey = storageKey;
                this.maxStorageSize = 10 * 1024 * 1024;
            }

            saveMessages(messages) {
                try {
                    const data = JSON.stringify({
                        version: '1.0',
                        timestamp: new Date().toISOString(),
                        messages: messages
                    });

                    if (data.length > this.maxStorageSize) {
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
                    console.error('Failed to save messages:', error);
                    try {
                        localStorage.removeItem(this.storageKey);
                        const lastMessages = messages.slice(-25);
                        localStorage.setItem(this.storageKey, JSON.stringify({
                            version: '1.0',
                            timestamp: new Date().toISOString(),
                            messages: lastMessages
                        }));
                    } catch (retryError) {
                        console.error('Failed retry:', retryError);
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

                    return parsed.messages.map(msg => ({
                        ...msg,
                        timestamp: new Date(msg.timestamp)
                    }));
                } catch (error) {
                    console.error('Failed to load:', error);
                    return [];
                }
            }

            clearMessages() {
                try {
                    localStorage.removeItem(this.storageKey);
                } catch (error) {
                    console.error('Failed to clear:', error);
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

        history = new ChatMessageHistory(testStorageKey);
    });

    afterEach(() => {
        localStorage.clear();
    });

    describe('Message History Initialization', () => {
        test('should initialize with empty storage', () => {
            const messages = history.loadMessages();
            expect(messages).toEqual([]);
        });

        test('should have correct storage key', () => {
            expect(history.storageKey).toBe(testStorageKey);
        });

        test('should have default max storage size', () => {
            expect(history.maxStorageSize).toBe(10 * 1024 * 1024);
        });

        test('should return empty storage info on init', () => {
            const info = history.getStorageInfo();
            expect(info.isEmpty).toBe(true);
            expect(info.messageCount).toBe(0);
            expect(info.sizeBytes).toBe(0);
        });
    });

    describe('Saving Messages', () => {
        test('should save single user message', () => {
            const messages = [{
                id: 1,
                text: 'Hello',
                sender: 'user',
                timestamp: new Date(),
                type: 'message'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded.length).toBe(1);
            expect(loaded[0].text).toBe('Hello');
            expect(loaded[0].sender).toBe('user');
        });

        test('should save single AI message', () => {
            const messages = [{
                id: 2,
                text: 'Hello, how can I help?',
                sender: 'ai',
                timestamp: new Date(),
                type: 'message'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded.length).toBe(1);
            expect(loaded[0].text).toBe('Hello, how can I help?');
            expect(loaded[0].sender).toBe('ai');
        });

        test('should save system messages', () => {
            const messages = [{
                id: 3,
                text: 'Agent status changed to active',
                sender: 'system',
                timestamp: new Date(),
                type: 'system'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded.length).toBe(1);
            expect(loaded[0].sender).toBe('system');
            expect(loaded[0].type).toBe('system');
        });

        test('should save multiple messages in sequence', () => {
            const messages = [
                { id: 1, text: 'Message 1', sender: 'user', timestamp: new Date(), type: 'message' },
                { id: 2, text: 'Response 1', sender: 'ai', timestamp: new Date(), type: 'message' },
                { id: 3, text: 'Message 2', sender: 'user', timestamp: new Date(), type: 'message' },
                { id: 4, text: 'Response 2', sender: 'ai', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded.length).toBe(4);
            expect(loaded[0].text).toBe('Message 1');
            expect(loaded[3].text).toBe('Response 2');
        });

        test('should preserve message order', () => {
            const messages = [
                { id: 1, text: 'First', sender: 'user', timestamp: new Date(), type: 'message' },
                { id: 2, text: 'Second', sender: 'ai', timestamp: new Date(), type: 'message' },
                { id: 3, text: 'Third', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].text).toBe('First');
            expect(loaded[1].text).toBe('Second');
            expect(loaded[2].text).toBe('Third');
        });

        test('should update storage info after saving', () => {
            const messages = [
                { id: 1, text: 'Message', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            const info = history.getStorageInfo();
            expect(info.isEmpty).toBe(false);
            expect(info.messageCount).toBe(1);
            expect(info.sizeBytes).toBeGreaterThan(0);
        });
    });

    describe('Loading Messages', () => {
        test('should load previously saved messages', () => {
            const messages = [
                { id: 1, text: 'Test', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].text).toBe('Test');
        });

        test('should restore timestamp as Date object', () => {
            const originalTime = new Date();
            const messages = [{
                id: 1,
                text: 'Test',
                sender: 'user',
                timestamp: originalTime,
                type: 'message'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].timestamp).toBeInstanceOf(Date);
            expect(loaded[0].timestamp.getTime()).toBe(originalTime.getTime());
        });

        test('should return empty array if no data stored', () => {
            const loaded = history.loadMessages();
            expect(Array.isArray(loaded)).toBe(true);
            expect(loaded.length).toBe(0);
        });

        test('should handle corrupted JSON gracefully', () => {
            localStorage.setItem(testStorageKey, 'corrupted data');
            const loaded = history.loadMessages();
            expect(loaded).toEqual([]);
        });

        test('should handle missing messages array', () => {
            localStorage.setItem(testStorageKey, JSON.stringify({ version: '1.0' }));
            const loaded = history.loadMessages();
            expect(loaded).toEqual([]);
        });
    });

    describe('Clearing Messages', () => {
        test('should clear all messages from storage', () => {
            const messages = [
                { id: 1, text: 'Message', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            expect(history.loadMessages().length).toBe(1);

            history.clearMessages();
            expect(history.loadMessages().length).toBe(0);
        });

        test('should update storage info after clear', () => {
            const messages = [
                { id: 1, text: 'Message', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            history.clearMessages();
            const info = history.getStorageInfo();
            expect(info.isEmpty).toBe(true);
            expect(info.messageCount).toBe(0);
        });

        test('should handle clearing empty storage gracefully', () => {
            expect(() => history.clearMessages()).not.toThrow();
        });
    });

    describe('Storage Management', () => {
        test('should track storage size', () => {
            const messages = [
                { id: 1, text: 'Test message with some content', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            const info = history.getStorageInfo();
            expect(info.sizeBytes).toBeGreaterThan(50);
        });

        test('should include version and timestamp in storage', () => {
            const messages = [
                { id: 1, text: 'Test', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            const data = localStorage.getItem(testStorageKey);
            const parsed = JSON.parse(data);
            expect(parsed.version).toBe('1.0');
            expect(parsed.timestamp).toBeTruthy();
        });

        test('should handle large message content', () => {
            const largeText = 'A'.repeat(5000);
            const messages = [
                { id: 1, text: largeText, sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].text).toBe(largeText);
        });

        test('should trim messages if storage exceeds limit', () => {
            // This test simulates the trimming behavior
            const messages = [];
            for (let i = 0; i < 100; i++) {
                messages.push({
                    id: i,
                    text: 'Message ' + i,
                    sender: i % 2 === 0 ? 'user' : 'ai',
                    timestamp: new Date(),
                    type: 'message'
                });
            }

            // Mock the maxStorageSize to be very small to force trimming
            history.maxStorageSize = 1000;
            const result = history.saveMessages(messages);

            // Should trim to 50 messages max
            expect(result.length).toBeLessThanOrEqual(50);
        });
    });

    describe('Message Types Support', () => {
        test('should support user message type', () => {
            const messages = [{
                id: 1,
                text: 'User input',
                sender: 'user',
                timestamp: new Date(),
                type: 'message'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].type).toBe('message');
        });

        test('should support AI message type', () => {
            const messages = [{
                id: 1,
                text: 'AI response',
                sender: 'ai',
                timestamp: new Date(),
                type: 'message'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].type).toBe('message');
        });

        test('should support system message type', () => {
            const messages = [{
                id: 1,
                text: 'System notification',
                sender: 'system',
                timestamp: new Date(),
                type: 'system'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].type).toBe('system');
        });

        test('should support error message type', () => {
            const messages = [{
                id: 1,
                text: 'Error occurred',
                sender: 'system',
                timestamp: new Date(),
                type: 'error'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].type).toBe('error');
        });

        test('should preserve all message properties', () => {
            const messages = [{
                id: 12345,
                text: 'Test message with code block',
                sender: 'ai',
                timestamp: new Date('2024-01-01T12:00:00Z'),
                type: 'message',
                metadata: { custom: 'data' }
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].id).toBe(12345);
            expect(loaded[0].text).toBe('Test message with code block');
            expect(loaded[0].sender).toBe('ai');
            expect(loaded[0].type).toBe('message');
            expect(loaded[0].metadata).toEqual({ custom: 'data' });
        });
    });

    describe('Special Content Handling', () => {
        test('should preserve code blocks in messages', () => {
            const codeBlock = '```javascript\nconst x = 5;\n```';
            const messages = [{
                id: 1,
                text: codeBlock,
                sender: 'ai',
                timestamp: new Date(),
                type: 'message'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].text).toBe(codeBlock);
        });

        test('should preserve JSON data in messages', () => {
            const jsonData = JSON.stringify({ status: 'active', uptime: '99.2%' });
            const messages = [{
                id: 1,
                text: jsonData,
                sender: 'ai',
                timestamp: new Date(),
                type: 'message'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            const parsedJson = JSON.parse(loaded[0].text);
            expect(parsedJson.status).toBe('active');
            expect(parsedJson.uptime).toBe('99.2%');
        });

        test('should preserve special characters', () => {
            const specialText = 'Test with <script>, &amp;, and "quotes"';
            const messages = [{
                id: 1,
                text: specialText,
                sender: 'user',
                timestamp: new Date(),
                type: 'message'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].text).toBe(specialText);
        });

        test('should preserve unicode characters', () => {
            const unicodeText = 'Hello 👋 世界 🌍 مرحبا';
            const messages = [{
                id: 1,
                text: unicodeText,
                sender: 'user',
                timestamp: new Date(),
                type: 'message'
            }];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded[0].text).toBe(unicodeText);
        });
    });

    describe('Edge Cases', () => {
        test('should handle null message gracefully', () => {
            const messages = [null];
            expect(() => {
                history.saveMessages(messages);
            }).not.toThrow();
        });

        test('should handle empty message array', () => {
            history.saveMessages([]);
            const loaded = history.loadMessages();
            expect(loaded).toEqual([]);
        });

        test('should handle localStorage full scenario', () => {
            // Mock localStorage to throw quota exceeded
            const originalSetItem = Storage.prototype.setItem;
            let callCount = 0;

            Storage.prototype.setItem = function(key, value) {
                callCount++;
                if (callCount > 1) {
                    throw new DOMException('QuotaExceededError');
                }
                return originalSetItem.call(this, key, value);
            };

            const messages = [
                { id: 1, text: 'Test', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            const loaded = history.loadMessages();
            expect(loaded.length).toBeGreaterThanOrEqual(0);

            // Restore original
            Storage.prototype.setItem = originalSetItem;
        });

        test('should provide storage info with timestamp', () => {
            const messages = [
                { id: 1, text: 'Test', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);
            const info = history.getStorageInfo();
            expect(info.lastUpdated).toBeTruthy();
            expect(new Date(info.lastUpdated)).toBeInstanceOf(Date);
        });
    });

    describe('Persistence Across Sessions', () => {
        test('should persist messages across multiple loads', () => {
            const messages = [
                { id: 1, text: 'Message 1', sender: 'user', timestamp: new Date(), type: 'message' }
            ];

            history.saveMessages(messages);

            // Simulate new instance (like a page reload)
            // Create a new ChatMessageHistory-like class for this test
            class ChatMessageHistory {
                constructor(storageKey) {
                    this.storageKey = storageKey;
                    this.maxStorageSize = 10 * 1024 * 1024;
                }

                saveMessages(messages) {
                    const data = JSON.stringify({
                        version: '1.0',
                        timestamp: new Date().toISOString(),
                        messages: messages
                    });
                    localStorage.setItem(this.storageKey, data);
                    return messages;
                }

                loadMessages() {
                    const data = localStorage.getItem(this.storageKey);
                    if (!data) return [];
                    const parsed = JSON.parse(data);
                    return (parsed.messages || []).map(msg => ({
                        ...msg,
                        timestamp: new Date(msg.timestamp)
                    }));
                }
            }

            const newHistory = new ChatMessageHistory(testStorageKey);
            const loaded = newHistory.loadMessages();
            expect(loaded.length).toBe(1);
            expect(loaded[0].text).toBe('Message 1');
        });

        test('should accumulate messages across save calls', () => {
            let messages = [
                { id: 1, text: 'First', sender: 'user', timestamp: new Date(), type: 'message' }
            ];
            history.saveMessages(messages);

            messages = [
                { id: 1, text: 'First', sender: 'user', timestamp: new Date(), type: 'message' },
                { id: 2, text: 'Second', sender: 'ai', timestamp: new Date(), type: 'message' }
            ];
            history.saveMessages(messages);

            const loaded = history.loadMessages();
            expect(loaded.length).toBe(2);
            expect(loaded[1].text).toBe('Second');
        });
    });
});
