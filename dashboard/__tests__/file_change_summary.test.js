/**
 * Unit tests for FileChangeSummary component
 * AI-100: File Change Summary - List of Created/Modified/Deleted Files
 */

const { FileChangeSummary } = require('../file-change-summary.js');

describe('FileChangeSummary', () => {
    let fileChangeSummary;

    beforeEach(() => {
        fileChangeSummary = new FileChangeSummary();
    });

    describe('Constructor', () => {
        test('should initialize with empty expandedFiles set', () => {
            expect(fileChangeSummary.expandedFiles).toBeInstanceOf(Set);
            expect(fileChangeSummary.expandedFiles.size).toBe(0);
        });
    });

    describe('getLanguageFromPath', () => {
        test('should correctly identify JavaScript files', () => {
            expect(fileChangeSummary.getLanguageFromPath('test.js')).toBe('javascript');
            expect(fileChangeSummary.getLanguageFromPath('test.jsx')).toBe('javascript');
        });

        test('should correctly identify TypeScript files', () => {
            expect(fileChangeSummary.getLanguageFromPath('test.ts')).toBe('typescript');
            expect(fileChangeSummary.getLanguageFromPath('test.tsx')).toBe('typescript');
        });

        test('should correctly identify Python files', () => {
            expect(fileChangeSummary.getLanguageFromPath('test.py')).toBe('python');
        });

        test('should return plaintext for unknown extensions', () => {
            expect(fileChangeSummary.getLanguageFromPath('test.unknown')).toBe('plaintext');
            expect(fileChangeSummary.getLanguageFromPath('noextension')).toBe('plaintext');
        });

        test('should handle various language extensions', () => {
            expect(fileChangeSummary.getLanguageFromPath('test.java')).toBe('java');
            expect(fileChangeSummary.getLanguageFromPath('test.go')).toBe('go');
            expect(fileChangeSummary.getLanguageFromPath('test.rs')).toBe('rust');
            expect(fileChangeSummary.getLanguageFromPath('test.html')).toBe('html');
            expect(fileChangeSummary.getLanguageFromPath('test.css')).toBe('css');
            expect(fileChangeSummary.getLanguageFromPath('test.json')).toBe('json');
            expect(fileChangeSummary.getLanguageFromPath('test.md')).toBe('markdown');
        });
    });

    describe('generateFileId', () => {
        test('should generate valid ID from file path', () => {
            const id = fileChangeSummary.generateFileId('src/components/Test.tsx');
            expect(id).toBe('file-src-components-Test-tsx');
        });

        test('should replace special characters with hyphens', () => {
            const id = fileChangeSummary.generateFileId('src/test@file.js');
            expect(id).toBe('file-src-test-file-js');
        });

        test('should handle paths with spaces', () => {
            const id = fileChangeSummary.generateFileId('my file.txt');
            expect(id).toBe('file-my-file-txt');
        });
    });

    describe('categorizeFiles', () => {
        test('should categorize files by change type', () => {
            const files = [
                { path: 'new.js', changeType: 'created' },
                { path: 'modified.js', changeType: 'modified' },
                { path: 'old.js', changeType: 'deleted' },
                { path: 'another.js', changeType: 'modified' }
            ];

            const categorized = fileChangeSummary.categorizeFiles(files);

            expect(categorized.created).toHaveLength(1);
            expect(categorized.modified).toHaveLength(2);
            expect(categorized.deleted).toHaveLength(1);
        });

        test('should handle empty array', () => {
            const categorized = fileChangeSummary.categorizeFiles([]);

            expect(categorized.created).toHaveLength(0);
            expect(categorized.modified).toHaveLength(0);
            expect(categorized.deleted).toHaveLength(0);
        });
    });

    describe('sumLines', () => {
        test('should sum lines added across all categories', () => {
            const categorized = {
                created: [{ linesAdded: 10, linesRemoved: 0 }],
                modified: [{ linesAdded: 5, linesRemoved: 3 }, { linesAdded: 8, linesRemoved: 2 }],
                deleted: [{ linesAdded: 0, linesRemoved: 20 }]
            };

            const totalAdded = fileChangeSummary.sumLines(categorized, 'linesAdded');
            expect(totalAdded).toBe(23); // 10 + 5 + 8 + 0
        });

        test('should sum lines removed across all categories', () => {
            const categorized = {
                created: [{ linesAdded: 10, linesRemoved: 0 }],
                modified: [{ linesAdded: 5, linesRemoved: 3 }, { linesAdded: 8, linesRemoved: 2 }],
                deleted: [{ linesAdded: 0, linesRemoved: 20 }]
            };

            const totalRemoved = fileChangeSummary.sumLines(categorized, 'linesRemoved');
            expect(totalRemoved).toBe(25); // 0 + 3 + 2 + 20
        });
    });

    describe('countTotalFiles', () => {
        test('should count total files across all categories', () => {
            const categorized = {
                created: [{ path: 'a.js' }, { path: 'b.js' }],
                modified: [{ path: 'c.js' }],
                deleted: [{ path: 'd.js' }, { path: 'e.js' }, { path: 'f.js' }]
            };

            const total = fileChangeSummary.countTotalFiles(categorized);
            expect(total).toBe(6);
        });

        test('should return 0 for empty categories', () => {
            const categorized = {
                created: [],
                modified: [],
                deleted: []
            };

            const total = fileChangeSummary.countTotalFiles(categorized);
            expect(total).toBe(0);
        });
    });

    describe('escapeHtml', () => {
        test('should escape HTML special characters', () => {
            expect(fileChangeSummary.escapeHtml('<script>alert("xss")</script>'))
                .toBe('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
        });

        test('should escape ampersands', () => {
            expect(fileChangeSummary.escapeHtml('A & B')).toBe('A &amp; B');
        });

        test('should escape quotes', () => {
            expect(fileChangeSummary.escapeHtml('He said "hello"')).toBe('He said &quot;hello&quot;');
            expect(fileChangeSummary.escapeHtml("It's")).toBe('It&#039;s');
        });

        test('should handle empty string', () => {
            expect(fileChangeSummary.escapeHtml('')).toBe('');
        });
    });

    describe('createSummary', () => {
        test('should create summary HTML for valid file changes', () => {
            const changeData = {
                files: [
                    {
                        path: 'test.js',
                        changeType: 'created',
                        linesAdded: 10,
                        linesRemoved: 0,
                        diffContent: '@@ -0,0 +1,10 @@\n+console.log("test");',
                        language: 'javascript',
                        id: 'file-test-js'
                    }
                ]
            };

            const html = fileChangeSummary.createSummary(changeData);

            expect(html).toContain('file-change-summary');
            expect(html).toContain('File Changes Summary');
            expect(html).toContain('test.js');
            expect(html).toContain('+10');
        });

        test('should render empty state for no files', () => {
            const changeData = { files: [] };
            const html = fileChangeSummary.createSummary(changeData);

            expect(html).toContain('file-change-summary-empty');
            expect(html).toContain('No file changes to display');
        });

        test('should render empty state for null files', () => {
            const changeData = { files: null };
            const html = fileChangeSummary.createSummary(changeData);

            expect(html).toContain('file-change-summary-empty');
        });
    });

    describe('renderCategory', () => {
        test('should render category with files', () => {
            const files = [
                {
                    path: 'test.js',
                    changeType: 'created',
                    linesAdded: 10,
                    linesRemoved: 0,
                    diffContent: '',
                    language: 'javascript',
                    id: 'file-test-js'
                }
            ];

            const html = fileChangeSummary.renderCategory('Created', files, 'created');

            expect(html).toContain('file-category');
            expect(html).toContain('Created (1)');
            expect(html).toContain('test.js');
        });

        test('should return empty string for empty category', () => {
            const html = fileChangeSummary.renderCategory('Created', [], 'created');
            expect(html).toBe('');
        });
    });

    describe('renderFile', () => {
        test('should render file with stats', () => {
            const file = {
                path: 'src/test.js',
                changeType: 'modified',
                linesAdded: 15,
                linesRemoved: 8,
                diffContent: '@@ -1,5 +1,7 @@\n+new line',
                language: 'javascript',
                id: 'file-src-test-js'
            };

            const html = fileChangeSummary.renderFile(file, 'modified');

            expect(html).toContain('file-item');
            expect(html).toContain('src/test.js');
            expect(html).toContain('+15');
            expect(html).toContain('-8');
            expect(html).toContain('file-header-file-src-test-js');
        });

        test('should not show stats for zero values', () => {
            const file = {
                path: 'test.js',
                changeType: 'created',
                linesAdded: 0,
                linesRemoved: 0,
                diffContent: '',
                language: 'javascript',
                id: 'file-test-js'
            };

            const html = fileChangeSummary.renderFile(file, 'created');

            expect(html).not.toContain('+0');
            expect(html).not.toContain('-0');
        });
    });

    describe('renderDiff', () => {
        test('should render diff with added lines', () => {
            const file = {
                diffContent: '@@ -0,0 +1,3 @@\n+line 1\n+line 2\n+line 3',
                language: 'javascript'
            };

            const html = fileChangeSummary.renderDiff(file);

            expect(html).toContain('diff-content');
            expect(html).toContain('diff-line added');
            expect(html).toContain('line 1');
            expect(html).toContain('line 2');
            expect(html).toContain('line 3');
        });

        test('should render diff with deleted lines', () => {
            const file = {
                diffContent: '@@ -1,3 +0,0 @@\n-old line 1\n-old line 2\n-old line 3',
                language: 'javascript'
            };

            const html = fileChangeSummary.renderDiff(file);

            expect(html).toContain('diff-line deleted');
            expect(html).toContain('old line 1');
        });

        test('should render diff with context lines', () => {
            const file = {
                diffContent: '@@ -1,5 +1,5 @@\n context line\n-old line\n+new line\n context line',
                language: 'javascript'
            };

            const html = fileChangeSummary.renderDiff(file);

            expect(html).toContain('diff-line context');
            expect(html).toContain('context line');
        });

        test('should render hunk headers', () => {
            const file = {
                diffContent: '@@ -1,5 +1,7 @@\n+new line',
                language: 'javascript'
            };

            const html = fileChangeSummary.renderDiff(file);

            expect(html).toContain('diff-line hunk-header');
            expect(html).toContain('@@ -1,5 +1,7 @@');
        });

        test('should render empty state for no diff content', () => {
            const file = { diffContent: '' };
            const html = fileChangeSummary.renderDiff(file);

            expect(html).toContain('diff-empty');
            expect(html).toContain('No diff content available');
        });

        test('should escape HTML in diff content', () => {
            const file = {
                diffContent: '+<script>alert("xss")</script>',
                language: 'javascript'
            };

            const html = fileChangeSummary.renderDiff(file);

            expect(html).not.toContain('<script>');
            expect(html).toContain('&lt;script&gt;');
        });
    });

    describe('renderSummary', () => {
        test('should render complete summary with all categories', () => {
            const categorized = {
                created: [
                    {
                        path: 'new.js',
                        changeType: 'created',
                        linesAdded: 50,
                        linesRemoved: 0,
                        diffContent: '',
                        language: 'javascript',
                        id: 'file-new-js'
                    }
                ],
                modified: [
                    {
                        path: 'existing.js',
                        changeType: 'modified',
                        linesAdded: 10,
                        linesRemoved: 5,
                        diffContent: '',
                        language: 'javascript',
                        id: 'file-existing-js'
                    }
                ],
                deleted: [
                    {
                        path: 'old.js',
                        changeType: 'deleted',
                        linesAdded: 0,
                        linesRemoved: 30,
                        diffContent: '',
                        language: 'javascript',
                        id: 'file-old-js'
                    }
                ]
            };

            const html = fileChangeSummary.renderSummary(categorized);

            expect(html).toContain('file-change-summary');
            expect(html).toContain('File Changes Summary');
            expect(html).toContain('Created (1)');
            expect(html).toContain('Modified (1)');
            expect(html).toContain('Deleted (1)');
            expect(html).toContain('data-testid="total-files"');
            expect(html).toContain('data-testid="total-added"');
            expect(html).toContain('data-testid="total-removed"');
        });

        test('should calculate correct totals', () => {
            const categorized = {
                created: [{ linesAdded: 20, linesRemoved: 0 }],
                modified: [{ linesAdded: 10, linesRemoved: 5 }],
                deleted: [{ linesAdded: 0, linesRemoved: 15 }]
            };

            const html = fileChangeSummary.renderSummary(categorized);

            // Should show total of 30 lines added (20 + 10 + 0)
            expect(html).toContain('>30<');
            // Should show total of 20 lines removed (0 + 5 + 15)
            expect(html).toContain('>20<');
        });
    });

    describe('reset', () => {
        test('should clear expandedFiles set', () => {
            fileChangeSummary.expandedFiles.add('file-1');
            fileChangeSummary.expandedFiles.add('file-2');

            expect(fileChangeSummary.expandedFiles.size).toBe(2);

            fileChangeSummary.reset();

            expect(fileChangeSummary.expandedFiles.size).toBe(0);
        });
    });

    describe('extractFileInfo', () => {
        test('should extract file info from git diff block', () => {
            const block = `a/src/test.js b/src/test.js
index 1234567..abcdefg 100644
--- a/src/test.js
+++ b/src/test.js
@@ -1,5 +1,7 @@
 function test() {
-  return "old";
+  return "new";
+  console.log("added");
 }`;

            const lines = block.split('\n');
            const fileInfo = fileChangeSummary.extractFileInfo(block, lines);

            expect(fileInfo.path).toBe('src/test.js');
            expect(fileInfo.changeType).toBe('modified');
            expect(fileInfo.linesAdded).toBe(2); // +return "new" and +console.log
            expect(fileInfo.linesRemoved).toBe(1); // -return "old"
            expect(fileInfo.language).toBe('javascript');
        });

        test('should detect created files', () => {
            const block = `a/dev/null b/src/new-file.js
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/new-file.js
@@ -0,0 +1,5 @@
+function newFunc() {
+  return "new";
+}`;

            const lines = block.split('\n');
            const fileInfo = fileChangeSummary.extractFileInfo(block, lines);

            expect(fileInfo.changeType).toBe('created');
            expect(fileInfo.linesAdded).toBe(3);
            expect(fileInfo.linesRemoved).toBe(0);
        });

        test('should detect deleted files', () => {
            const block = `a/src/old-file.js b/dev/null
deleted file mode 100644
index 1234567..0000000
--- a/src/old-file.js
+++ /dev/null
@@ -1,10 +0,0 @@
-function oldFunc() {
-  return "old";
-}`;

            const lines = block.split('\n');
            const fileInfo = fileChangeSummary.extractFileInfo(block, lines);

            expect(fileInfo.changeType).toBe('deleted');
            expect(fileInfo.linesAdded).toBe(0);
            expect(fileInfo.linesRemoved).toBe(3);
        });
    });

    describe('Integration: Full workflow', () => {
        test('should handle complete file change workflow', () => {
            const changeData = {
                files: [
                    {
                        path: 'src/components/NewComponent.tsx',
                        changeType: 'created',
                        linesAdded: 45,
                        linesRemoved: 0,
                        diffContent: '@@ -0,0 +1,45 @@\n+import React from "react";',
                        language: 'typescript',
                        id: 'file-src-components-NewComponent-tsx'
                    },
                    {
                        path: 'src/utils/helper.js',
                        changeType: 'modified',
                        linesAdded: 12,
                        linesRemoved: 8,
                        diffContent: '@@ -5,10 +5,14 @@\n-old code\n+new code',
                        language: 'javascript',
                        id: 'file-src-utils-helper-js'
                    },
                    {
                        path: 'src/legacy/OldComponent.jsx',
                        changeType: 'deleted',
                        linesAdded: 0,
                        linesRemoved: 89,
                        diffContent: '@@ -1,89 +0,0 @@\n-deleted code',
                        language: 'javascript',
                        id: 'file-src-legacy-OldComponent-jsx'
                    }
                ]
            };

            const html = fileChangeSummary.createSummary(changeData);

            // Verify structure
            expect(html).toContain('file-change-summary');
            expect(html).toContain('File Changes Summary');

            // Verify stats
            expect(html).toContain('data-testid="total-files"');
            expect(html).toContain('>3<'); // 3 files
            expect(html).toContain('>57<'); // 45 + 12 + 0 lines added
            expect(html).toContain('>97<'); // 0 + 8 + 89 lines removed

            // Verify categories
            expect(html).toContain('Created (1)');
            expect(html).toContain('Modified (1)');
            expect(html).toContain('Deleted (1)');

            // Verify file paths
            expect(html).toContain('src/components/NewComponent.tsx');
            expect(html).toContain('src/utils/helper.js');
            expect(html).toContain('src/legacy/OldComponent.jsx');
        });
    });
});
