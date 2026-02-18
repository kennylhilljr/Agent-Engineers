/**
 * Unit tests for File Change Summary component
 * Tests the rendering and functionality of file change display
 */

describe('File Change Summary Component', () => {
    let container;

    beforeEach(() => {
        // Create a container for testing
        container = document.createElement('div');
        container.id = 'file-changes-container';
        document.body.appendChild(container);
    });

    afterEach(() => {
        // Clean up
        document.body.removeChild(container);
    });

    describe('Empty State', () => {
        test('should display empty state when no coding events exist', () => {
            // Mock empty events
            const events = [];

            // Call render function (assuming it's globally available)
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const emptyState = container.querySelector('[data-testid="file-changes-empty"]');
            expect(emptyState).toBeTruthy();
            expect(emptyState.textContent).toContain('No file changes yet');
        });

        test('should display empty state when no file changes in coding events', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: []
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const emptyState = container.querySelector('[data-testid="file-changes-empty"]');
            expect(emptyState).toBeTruthy();
        });

        test('should display empty state for non-coding events', () => {
            const events = [
                {
                    agent_name: 'github',
                    file_changes: []
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const emptyState = container.querySelector('[data-testid="file-changes-empty"]');
            expect(emptyState).toBeTruthy();
        });
    });

    describe('File Change Statistics', () => {
        test('should display correct counts for created/modified/deleted files', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'src/new-file.js',
                            change_type: 'created',
                            lines_added: 50,
                            lines_removed: 0,
                            language: 'javascript',
                            diff: '+console.log("test");'
                        },
                        {
                            path: 'src/existing-file.js',
                            change_type: 'modified',
                            lines_added: 10,
                            lines_removed: 5,
                            language: 'javascript',
                            diff: '-old line\n+new line'
                        },
                        {
                            path: 'src/old-file.js',
                            change_type: 'deleted',
                            lines_added: 0,
                            lines_removed: 30,
                            language: 'javascript',
                            diff: '-deleted content'
                        }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const createdCount = container.querySelector('[data-testid="files-created-count"]');
            const modifiedCount = container.querySelector('[data-testid="files-modified-count"]');
            const deletedCount = container.querySelector('[data-testid="files-deleted-count"]');

            expect(createdCount?.textContent).toBe('1');
            expect(modifiedCount?.textContent).toBe('1');
            expect(deletedCount?.textContent).toBe('1');
        });

        test('should display correct line count totals', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'file1.js',
                            change_type: 'modified',
                            lines_added: 25,
                            lines_removed: 10,
                            language: 'javascript',
                            diff: ''
                        },
                        {
                            path: 'file2.js',
                            change_type: 'modified',
                            lines_added: 35,
                            lines_removed: 20,
                            language: 'javascript',
                            diff: ''
                        }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const linesAdded = container.querySelector('[data-testid="total-lines-added"]');
            const linesRemoved = container.querySelector('[data-testid="total-lines-removed"]');

            expect(linesAdded?.textContent).toBe('+60');
            expect(linesRemoved?.textContent).toBe('-30');
        });
    });

    describe('File Change Items', () => {
        test('should render file change items with correct data', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'src/component.tsx',
                            change_type: 'created',
                            lines_added: 100,
                            lines_removed: 0,
                            language: 'typescript',
                            diff: '+import React from "react";'
                        }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const fileItems = container.querySelectorAll('[data-testid="file-change-item"]');
            expect(fileItems.length).toBe(1);

            const filePath = container.querySelector('[data-testid="file-path"]');
            expect(filePath?.textContent).toBe('src/component.tsx');

            const changeType = container.querySelector('[data-testid="file-change-type"]');
            expect(changeType?.textContent).toBe('Created');
        });

        test('should categorize files correctly (Created/Modified/Deleted)', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        { path: 'new.js', change_type: 'created', lines_added: 10, lines_removed: 0, language: 'javascript', diff: '' },
                        { path: 'mod.js', change_type: 'modified', lines_added: 5, lines_removed: 3, language: 'javascript', diff: '' },
                        { path: 'del.js', change_type: 'deleted', lines_added: 0, lines_removed: 10, language: 'javascript', diff: '' }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const changeTypes = container.querySelectorAll('[data-testid="file-change-type"]');
            expect(changeTypes[0]?.textContent).toBe('Created');
            expect(changeTypes[1]?.textContent).toBe('Modified');
            expect(changeTypes[2]?.textContent).toBe('Deleted');
        });
    });

    describe('Collapsible Diff View', () => {
        test('should have diff content collapsed by default', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'test.js',
                            change_type: 'modified',
                            lines_added: 5,
                            lines_removed: 2,
                            language: 'javascript',
                            diff: '+new line\n-old line'
                        }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const diffContent = container.querySelector('[data-testid="file-diff-content"]');
            expect(diffContent?.classList.contains('expanded')).toBe(false);
        });

        test('should toggle diff content when header is clicked', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'test.js',
                            change_type: 'modified',
                            lines_added: 5,
                            lines_removed: 2,
                            language: 'javascript',
                            diff: '+new line'
                        }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const diffContent = container.querySelector('[data-testid="file-diff-content"]');
            const fileHeader = diffContent?.previousElementSibling;

            // Initial state - collapsed
            expect(diffContent?.classList.contains('expanded')).toBe(false);

            // Click to expand
            if (fileHeader && typeof toggleFileDiff === 'function') {
                fileHeader.click();
                expect(diffContent?.classList.contains('expanded')).toBe(true);

                // Click to collapse
                fileHeader.click();
                expect(diffContent?.classList.contains('expanded')).toBe(false);
            }
        });
    });

    describe('Multiple File Types', () => {
        test('should handle multiple file types (JS, CSS, HTML, etc.)', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        { path: 'script.js', change_type: 'created', lines_added: 10, lines_removed: 0, language: 'javascript', diff: '' },
                        { path: 'style.css', change_type: 'modified', lines_added: 5, lines_removed: 2, language: 'css', diff: '' },
                        { path: 'index.html', change_type: 'modified', lines_added: 3, lines_removed: 1, language: 'html', diff: '' },
                        { path: 'component.tsx', change_type: 'created', lines_added: 50, lines_removed: 0, language: 'typescript', diff: '' }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const filePaths = container.querySelectorAll('[data-testid="file-path"]');
            expect(filePaths.length).toBe(4);
            expect(filePaths[0]?.textContent).toContain('.js');
            expect(filePaths[1]?.textContent).toContain('.css');
            expect(filePaths[2]?.textContent).toContain('.html');
            expect(filePaths[3]?.textContent).toContain('.tsx');
        });
    });

    describe('Diff Syntax Highlighting', () => {
        test('should render diff with proper line formatting', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'test.js',
                            change_type: 'modified',
                            lines_added: 2,
                            lines_removed: 1,
                            language: 'javascript',
                            diff: '@@ -1,3 +1,4 @@\n-old line\n+new line 1\n+new line 2\n context line'
                        }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const diffViewer = container.querySelector('.diff-viewer');
            expect(diffViewer).toBeTruthy();

            // Check for diff lines
            const diffLines = diffViewer?.querySelectorAll('.diff-line');
            expect(diffLines && diffLines.length > 0).toBe(true);
        });

        test('should differentiate added, removed, and context lines', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'test.js',
                            change_type: 'modified',
                            lines_added: 1,
                            lines_removed: 1,
                            language: 'javascript',
                            diff: '-removed line\n+added line\ncontext line'
                        }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const diffViewer = container.querySelector('.diff-viewer');
            const addedLines = diffViewer?.querySelectorAll('.diff-line.added');
            const removedLines = diffViewer?.querySelectorAll('.diff-line.removed');
            const contextLines = diffViewer?.querySelectorAll('.diff-line.context');

            expect(addedLines && addedLines.length > 0).toBe(true);
            expect(removedLines && removedLines.length > 0).toBe(true);
        });
    });

    describe('Edge Cases', () => {
        test('should handle null or undefined events gracefully', () => {
            if (typeof renderFileChanges === 'function') {
                renderFileChanges(null);
            }

            const emptyState = container.querySelector('[data-testid="file-changes-empty"]');
            expect(emptyState).toBeTruthy();
        });

        test('should handle events with missing file_changes field', () => {
            const events = [
                {
                    agent_name: 'coding'
                    // missing file_changes field
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const emptyState = container.querySelector('[data-testid="file-changes-empty"]');
            expect(emptyState).toBeTruthy();
        });

        test('should handle files with empty diff', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        {
                            path: 'test.js',
                            change_type: 'modified',
                            lines_added: 0,
                            lines_removed: 0,
                            language: 'javascript',
                            diff: ''
                        }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const fileItems = container.querySelectorAll('[data-testid="file-change-item"]');
            expect(fileItems.length).toBe(1);
        });

        test('should use most recent coding event when multiple exist', () => {
            const events = [
                {
                    agent_name: 'coding',
                    file_changes: [
                        { path: 'old.js', change_type: 'created', lines_added: 10, lines_removed: 0, language: 'javascript', diff: '' }
                    ]
                },
                {
                    agent_name: 'coding',
                    file_changes: [
                        { path: 'new.js', change_type: 'created', lines_added: 20, lines_removed: 0, language: 'javascript', diff: '' }
                    ]
                }
            ];

            if (typeof renderFileChanges === 'function') {
                renderFileChanges(events);
            }

            const filePath = container.querySelector('[data-testid="file-path"]');
            expect(filePath?.textContent).toBe('new.js');
        });
    });
});
