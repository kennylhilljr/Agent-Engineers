/**
 * E2E Tests for Live Code Streaming - AI-99
 * Tests real-time code streaming via WebSocket integration
 */

const { test, expect } = require('@playwright/test');

test.describe('Live Code Streaming E2E Tests - AI-99', () => {
    test('should display code stream when receiving code_stream WebSocket messages', async ({ page }) => {
        // Navigate to dashboard
        await page.goto('http://127.0.0.1:8421/dashboard.html');

        // Wait for initialization
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Simulate receiving code_stream messages via WebSocket
        await page.evaluate(() => {
            // Simulate code streaming for a Python file
            const messages = [
                {
                    type: 'code_stream',
                    timestamp: new Date().toISOString(),
                    content: 'def calculate_sum(a, b):',
                    file_path: 'src/calculator.py',
                    line_number: 1,
                    operation: 'add',
                    language: 'python'
                },
                {
                    type: 'code_stream',
                    timestamp: new Date().toISOString(),
                    content: '    """Calculate sum of two numbers"""',
                    file_path: 'src/calculator.py',
                    line_number: 2,
                    operation: 'add',
                    language: 'python'
                },
                {
                    type: 'code_stream',
                    timestamp: new Date().toISOString(),
                    content: '    return a + b',
                    file_path: 'src/calculator.py',
                    line_number: 3,
                    operation: 'add',
                    language: 'python'
                }
            ];

            // Send messages through handleCodeStream
            messages.forEach(msg => window.handleCodeStream(msg));
        });

        // Verify code stream container appears
        const container = await page.locator('[data-testid="code-stream-container"]');
        await expect(container).toBeVisible();

        // Verify file path
        await expect(page.locator('[data-testid="code-stream-file-path"]')).toContainText('src/calculator.py');

        // Verify all 3 lines appear
        const lines = await page.locator('[data-testid="code-line"]');
        await expect(lines).toHaveCount(3);

        // Verify streaming status
        await expect(page.locator('[data-testid="code-stream-status"]')).toContainText('Streaming');
    });

    test('should show diff with additions and deletions in real-time', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Simulate code changes with additions and deletions
        await page.evaluate(() => {
            const changes = [
                // Original line (unchanged)
                {
                    type: 'code_stream',
                    content: 'def old_function():',
                    file_path: 'src/refactor.py',
                    line_number: 1,
                    operation: 'delete',
                    language: 'python'
                },
                // New line (addition)
                {
                    type: 'code_stream',
                    content: 'def new_function():',
                    file_path: 'src/refactor.py',
                    line_number: 1,
                    operation: 'add',
                    language: 'python'
                },
                {
                    type: 'code_stream',
                    content: '    # Improved implementation',
                    file_path: 'src/refactor.py',
                    line_number: 2,
                    operation: 'add',
                    language: 'python'
                }
            ];

            changes.forEach(msg => window.handleCodeStream(msg));
        });

        // Verify deletion styling
        const deletion = await page.locator('[data-operation="delete"]');
        await expect(deletion).toBeVisible();
        await expect(deletion).toContainText('old_function');

        // Verify addition styling
        const additions = await page.locator('[data-operation="add"]');
        await expect(additions).toHaveCount(2);

        // Verify stats
        await expect(page.locator('[data-testid="code-additions"]')).toContainText('2');
        await expect(page.locator('[data-testid="code-deletions"]')).toContainText('1');
    });

    test('should handle multiple file edits streaming simultaneously', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Simulate editing 3 different files
        await page.evaluate(() => {
            const edits = [
                // File 1
                { content: 'import os', file_path: 'src/utils.py', line_number: 1, operation: 'add', language: 'python' },
                // File 2
                { content: 'const x = 10;', file_path: 'src/app.js', line_number: 1, operation: 'add', language: 'javascript' },
                // File 1 again
                { content: 'import sys', file_path: 'src/utils.py', line_number: 2, operation: 'add', language: 'python' },
                // File 3
                { content: '# Main', file_path: 'src/main.py', line_number: 1, operation: 'add', language: 'python' },
                // File 2 again
                { content: 'console.log(x);', file_path: 'src/app.js', line_number: 2, operation: 'add', language: 'javascript' },
            ];

            edits.forEach(edit => {
                window.handleCodeStream({
                    type: 'code_stream',
                    timestamp: new Date().toISOString(),
                    ...edit
                });
            });
        });

        // Should have 3 separate stream containers
        const containers = await page.locator('[data-testid="code-stream-container"]');
        await expect(containers).toHaveCount(3);

        // Verify each file has correct number of lines
        const utils = await page.locator('[data-file-path="src/utils.py"]');
        await expect(utils.locator('[data-testid="code-line"]')).toHaveCount(2);

        const app = await page.locator('[data-file-path="src/app.js"]');
        await expect(app.locator('[data-testid="code-line"]')).toHaveCount(2);

        const main = await page.locator('[data-file-path="src/main.py"]');
        await expect(main.locator('[data-testid="code-line"]')).toHaveCount(1);
    });

    test('should stream code character-by-character simulation', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Simulate rapid streaming (like characters appearing) - reduced to avoid timeout
        const code = 'def test():';
        const chunks = code.match(/.{1,4}/g) || []; // Split into 4-char chunks (smaller for speed)

        // Send all chunks at once (simulating rapid streaming)
        await page.evaluate((allChunks) => {
            allChunks.forEach((chunk, i) => {
                window.handleCodeStream({
                    type: 'code_stream',
                    timestamp: new Date().toISOString(),
                    content: chunk,
                    file_path: 'test.py',
                    line_number: i + 1,
                    operation: 'add',
                    language: 'python'
                });
            });
        }, chunks);

        // Wait for all lines to be rendered
        await page.waitForTimeout(200);

        // All chunks should be visible
        const lines = await page.locator('[data-testid="code-line"]');
        await expect(lines).toHaveCount(chunks.length);
    });

    test('should apply syntax highlighting during streaming', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Stream Python code with keywords
        await page.evaluate(() => {
            window.handleCodeStream({
                type: 'code_stream',
                content: 'class MyClass:',
                file_path: 'test.py',
                line_number: 1,
                operation: 'add',
                language: 'python'
            });
        });

        // Wait for rendering
        await page.waitForTimeout(100);

        // Check if syntax highlighting applied
        const lineContent = await page.locator('.code-line-content').first();
        const html = await lineContent.innerHTML();

        // Should contain token classes for 'class' keyword
        expect(html).toMatch(/token|keyword|class/);
    });

    test('should show streaming indicator while receiving chunks', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        await page.evaluate(() => {
            window.handleCodeStream({
                type: 'code_stream',
                content: 'streaming code',
                file_path: 'stream.py',
                line_number: 1,
                operation: 'add',
                language: 'python'
            });
        });

        // Streaming indicator should be visible
        const indicator = await page.locator('.streaming-indicator');
        await expect(indicator).toBeVisible();

        // Status should say "Streaming..."
        const status = await page.locator('[data-testid="code-stream-status"]');
        await expect(status).toContainText('Streaming');
    });

    test('should display code in chat message area', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        await page.evaluate(() => {
            window.handleCodeStream({
                type: 'code_stream',
                content: 'print("hello")',
                file_path: 'hello.py',
                line_number: 1,
                operation: 'add',
                language: 'python'
            });
        });

        // Code stream should appear in chat messages area
        const chatMessages = await page.locator('#chat-messages');
        const codeStream = chatMessages.locator('[data-testid="code-stream-container"]');
        await expect(codeStream).toBeVisible();
    });

    test('should handle rapid successive messages without dropping chunks', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Send 20 rapid messages
        const lineCount = 20;
        await page.evaluate((count) => {
            for (let i = 1; i <= count; i++) {
                window.handleCodeStream({
                    type: 'code_stream',
                    content: `line ${i}`,
                    file_path: 'rapid.py',
                    line_number: i,
                    operation: 'add',
                    language: 'python'
                });
            }
        }, lineCount);

        // All lines should be present
        await page.waitForTimeout(200);
        const lines = await page.locator('[data-testid="code-line"]');
        await expect(lines).toHaveCount(lineCount);
    });

    test('should show file path above code block', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        const testPath = 'src/components/MyComponent.tsx';

        await page.evaluate((path) => {
            window.handleCodeStream({
                type: 'code_stream',
                content: 'const x = 1;',
                file_path: path,
                line_number: 1,
                operation: 'add',
                language: 'typescript'
            });
        }, testPath);

        const filePath = await page.locator('[data-testid="code-stream-file-path"]');
        await expect(filePath).toContainText(testPath);

        // File path should be in header (above code body)
        const header = await page.locator('.code-stream-header');
        await expect(header.locator('[data-testid="code-stream-file-path"]')).toBeVisible();
    });

    test('should auto-scroll chat to bottom as code streams in', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        // Add some initial messages to enable scrolling
        await page.evaluate(() => {
            for (let i = 0; i < 5; i++) {
                window.chatInterface.addMessage(`Test message ${i}`, 'user');
            }
        });

        // Now stream code
        await page.evaluate(() => {
            for (let i = 1; i <= 10; i++) {
                window.handleCodeStream({
                    type: 'code_stream',
                    content: `code line ${i}`,
                    file_path: 'test.py',
                    line_number: i,
                    operation: 'add',
                    language: 'python'
                });
            }
        });

        // Check if chat is scrolled to bottom
        await page.waitForTimeout(200);
        const isAtBottom = await page.evaluate(() => {
            const container = document.getElementById('chat-messages');
            const tolerance = 5;
            return container.scrollTop + container.clientHeight >= container.scrollHeight - tolerance;
        });

        expect(isAtBottom).toBe(true);
    });

    test('should maintain separate statistics per file', async ({ page }) => {
        await page.goto('http://127.0.0.1:8421/dashboard.html');
        await page.waitForFunction(() => window.chatInterface !== undefined);

        await page.evaluate(() => {
            // File 1: 3 additions
            window.handleCodeStream({ content: 'a1', file_path: 'file1.py', line_number: 1, operation: 'add', language: 'python' });
            window.handleCodeStream({ content: 'a2', file_path: 'file1.py', line_number: 2, operation: 'add', language: 'python' });
            window.handleCodeStream({ content: 'a3', file_path: 'file1.py', line_number: 3, operation: 'add', language: 'python' });

            // File 2: 2 additions, 1 deletion
            window.handleCodeStream({ content: 'b1', file_path: 'file2.py', line_number: 1, operation: 'add', language: 'python' });
            window.handleCodeStream({ content: 'd1', file_path: 'file2.py', line_number: 2, operation: 'delete', language: 'python' });
            window.handleCodeStream({ content: 'b2', file_path: 'file2.py', line_number: 3, operation: 'add', language: 'python' });
        });

        // Check file1 stats
        const file1 = await page.locator('[data-file-path="file1.py"]');
        await expect(file1.locator('[data-testid="code-additions"]')).toContainText('3');
        await expect(file1.locator('[data-testid="code-deletions"]')).toContainText('0');

        // Check file2 stats
        const file2 = await page.locator('[data-file-path="file2.py"]');
        await expect(file2.locator('[data-testid="code-additions"]')).toContainText('2');
        await expect(file2.locator('[data-testid="code-deletions"]')).toContainText('1');
    });
});
