/**
 * Screenshot Tests for Code Streaming - AI-99
 * Captures visual evidence of code streaming functionality
 */

const { test, expect } = require('@playwright/test');

test.describe('Code Streaming Screenshot Tests - AI-99', () => {
    test('should capture screenshot of code streaming with syntax highlighting and diff', async ({ page }) => {
        // Navigate to dashboard
        await page.goto('http://127.0.0.1:8421/dashboard.html');

        // Wait for initialization
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Simulate a realistic code stream with additions and deletions
        await page.evaluate(() => {
            const codeChanges = [
                // File 1: Python file with additions
                { content: '# User Authentication Module', file_path: 'src/auth/user_auth.py', line_number: 1, operation: 'add', language: 'python' },
                { content: 'import bcrypt', file_path: 'src/auth/user_auth.py', line_number: 2, operation: 'add', language: 'python' },
                { content: 'from database import db', file_path: 'src/auth/user_auth.py', line_number: 3, operation: 'add', language: 'python' },
                { content: '', file_path: 'src/auth/user_auth.py', line_number: 4, operation: 'add', language: 'python' },
                { content: 'class UserAuthenticator:', file_path: 'src/auth/user_auth.py', line_number: 5, operation: 'add', language: 'python' },
                { content: '    def __init__(self, db_connection):', file_path: 'src/auth/user_auth.py', line_number: 6, operation: 'add', language: 'python' },
                { content: '        self.db = db_connection', file_path: 'src/auth/user_auth.py', line_number: 7, operation: 'add', language: 'python' },
                { content: '', file_path: 'src/auth/user_auth.py', line_number: 8, operation: 'add', language: 'python' },
                { content: '    def hash_password(self, password):', file_path: 'src/auth/user_auth.py', line_number: 9, operation: 'add', language: 'python' },
                { content: '        """Hash password using bcrypt"""', file_path: 'src/auth/user_auth.py', line_number: 10, operation: 'add', language: 'python' },
                { content: '        return bcrypt.hashpw(password.encode(), bcrypt.gensalt())', file_path: 'src/auth/user_auth.py', line_number: 11, operation: 'add', language: 'python' },

                // File 2: JavaScript with deletions and additions (refactoring)
                { content: 'function validateUser(user) {', file_path: 'src/frontend/validation.js', line_number: 1, operation: 'delete', language: 'javascript' },
                { content: 'const validateUser = (user) => {', file_path: 'src/frontend/validation.js', line_number: 1, operation: 'add', language: 'javascript' },
                { content: '  if (!user.email || !user.password) {', file_path: 'src/frontend/validation.js', line_number: 2, operation: 'add', language: 'javascript' },
                { content: '    throw new Error("Missing credentials");', file_path: 'src/frontend/validation.js', line_number: 3, operation: 'add', language: 'javascript' },
                { content: '  }', file_path: 'src/frontend/validation.js', line_number: 4, operation: 'add', language: 'javascript' },
                { content: '  return true;', file_path: 'src/frontend/validation.js', line_number: 5, operation: 'add', language: 'javascript' },
                { content: '}', file_path: 'src/frontend/validation.js', line_number: 6, operation: 'add', language: 'javascript' },
            ];

            // Send all code changes
            codeChanges.forEach(change => {
                window.handleCodeStream({
                    type: 'code_stream',
                    timestamp: new Date().toISOString(),
                    ...change
                });
            });
        });

        // Wait for rendering
        await page.waitForTimeout(500);

        // Verify streams exist
        const containers = await page.locator('[data-testid="code-stream-container"]');
        await expect(containers).toHaveCount(2);

        // Capture full page screenshot
        await page.screenshot({
            path: 'screenshots/ai-99-code-streaming-full.png',
            fullPage: true
        });

        // Capture just the code streaming area (chat messages)
        const chatMessages = await page.locator('#chat-messages');
        await chatMessages.screenshot({
            path: 'screenshots/ai-99-code-streaming-chat.png'
        });

        // Capture individual stream containers
        const pythonStream = await page.locator('[data-file-path="src/auth/user_auth.py"]');
        await pythonStream.screenshot({
            path: 'screenshots/ai-99-code-streaming-python.png'
        });

        const jsStream = await page.locator('[data-file-path="src/frontend/validation.js"]');
        await jsStream.screenshot({
            path: 'screenshots/ai-99-code-streaming-javascript.png'
        });

        console.log('Screenshots saved:');
        console.log('  - screenshots/ai-99-code-streaming-full.png');
        console.log('  - screenshots/ai-99-code-streaming-chat.png');
        console.log('  - screenshots/ai-99-code-streaming-python.png');
        console.log('  - screenshots/ai-99-code-streaming-javascript.png');
    });

    test('should capture streaming indicator in action', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Add one code chunk to show streaming status
        await page.evaluate(() => {
            window.handleCodeStream({
                type: 'code_stream',
                timestamp: new Date().toISOString(),
                content: 'def streaming_function():',
                file_path: 'src/example.py',
                line_number: 1,
                operation: 'add',
                language: 'python'
            });
        });

        await page.waitForTimeout(200);

        // Capture streaming indicator
        const streamStatus = await page.locator('[data-testid="code-stream-status"]');
        await streamStatus.screenshot({
            path: 'screenshots/ai-99-streaming-indicator.png'
        });

        console.log('Screenshot saved: screenshots/ai-99-streaming-indicator.png');
    });

    test('should capture diff highlighting (additions and deletions)', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Create a clear diff example
        await page.evaluate(() => {
            const diffExample = [
                { content: 'def old_implementation():', file_path: 'src/refactored.py', line_number: 1, operation: 'delete', language: 'python' },
                { content: '    print("Old way")', file_path: 'src/refactored.py', line_number: 2, operation: 'delete', language: 'python' },
                { content: '    return None', file_path: 'src/refactored.py', line_number: 3, operation: 'delete', language: 'python' },
                { content: 'def new_implementation():', file_path: 'src/refactored.py', line_number: 1, operation: 'add', language: 'python' },
                { content: '    """Improved implementation with better error handling"""', file_path: 'src/refactored.py', line_number: 2, operation: 'add', language: 'python' },
                { content: '    logger.info("New way")', file_path: 'src/refactored.py', line_number: 3, operation: 'add', language: 'python' },
                { content: '    return {"status": "success"}', file_path: 'src/refactored.py', line_number: 4, operation: 'add', language: 'python' },
            ];

            diffExample.forEach(change => {
                window.handleCodeStream({
                    type: 'code_stream',
                    timestamp: new Date().toISOString(),
                    ...change
                });
            });
        });

        await page.waitForTimeout(300);

        // Capture the diff
        const diffStream = await page.locator('[data-file-path="src/refactored.py"]');
        await diffStream.screenshot({
            path: 'screenshots/ai-99-diff-highlighting.png'
        });

        console.log('Screenshot saved: screenshots/ai-99-diff-highlighting.png');
    });

    test('should capture syntax highlighting for multiple languages', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Show syntax highlighting across different languages
        await page.evaluate(() => {
            const multiLanguage = [
                // Python
                { content: 'async def fetch_data(url):', file_path: 'api/client.py', line_number: 1, operation: 'add', language: 'python' },
                { content: '    response = await http.get(url)', file_path: 'api/client.py', line_number: 2, operation: 'add', language: 'python' },
                { content: '    return response.json()', file_path: 'api/client.py', line_number: 3, operation: 'add', language: 'python' },

                // JavaScript
                { content: 'const fetchData = async (url) => {', file_path: 'api/client.js', line_number: 1, operation: 'add', language: 'javascript' },
                { content: '  const response = await fetch(url);', file_path: 'api/client.js', line_number: 2, operation: 'add', language: 'javascript' },
                { content: '  return response.json();', file_path: 'api/client.js', line_number: 3, operation: 'add', language: 'javascript' },
                { content: '};', file_path: 'api/client.js', line_number: 4, operation: 'add', language: 'javascript' },

                // TypeScript
                { content: 'interface User {', file_path: 'types/user.ts', line_number: 1, operation: 'add', language: 'typescript' },
                { content: '  id: number;', file_path: 'types/user.ts', line_number: 2, operation: 'add', language: 'typescript' },
                { content: '  email: string;', file_path: 'types/user.ts', line_number: 3, operation: 'add', language: 'typescript' },
                { content: '}', file_path: 'types/user.ts', line_number: 4, operation: 'add', language: 'typescript' },
            ];

            multiLanguage.forEach(change => {
                window.handleCodeStream({
                    type: 'code_stream',
                    timestamp: new Date().toISOString(),
                    ...change
                });
            });
        });

        await page.waitForTimeout(400);

        // Capture all language streams
        await page.screenshot({
            path: 'screenshots/ai-99-multi-language-syntax.png',
            fullPage: true
        });

        console.log('Screenshot saved: screenshots/ai-99-multi-language-syntax.png');
    });
});
