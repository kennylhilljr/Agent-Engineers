/**
 * File Change Summary Component
 * AI-100: Display file changes after coding delegation completes
 *
 * Features:
 * - List of files created/modified/deleted
 * - Line counts (added/removed)
 * - Collapsible diff view for each file
 * - Syntax highlighting in diffs
 */

class FileChangeSummary {
    constructor() {
        this.expandedFiles = new Set();
    }

    /**
     * Parse git diff output and extract file changes
     * @param {string} diffOutput - Raw git diff output
     * @returns {Array} Array of file change objects
     */
    parseDiff(diffOutput) {
        const files = [];
        const fileBlocks = diffOutput.split('diff --git');

        fileBlocks.forEach((block, index) => {
            if (index === 0 && !block.trim()) return;

            const lines = block.split('\n');
            const fileInfo = this.extractFileInfo(block, lines);

            if (fileInfo) {
                files.push(fileInfo);
            }
        });

        return files;
    }

    /**
     * Extract file information from a diff block
     * @param {string} block - The diff block
     * @param {Array} lines - Lines of the block
     * @returns {Object} File change information
     */
    extractFileInfo(block, lines) {
        let filePath = '';
        let changeType = 'modified';
        let linesAdded = 0;
        let linesRemoved = 0;
        let diffContent = '';

        // Extract file path
        const pathMatch = block.match(/a\/(.+?)\s+b\/(.+)/);
        if (pathMatch) {
            filePath = pathMatch[2] || pathMatch[1];
        }

        // Determine change type
        if (block.includes('new file mode')) {
            changeType = 'created';
        } else if (block.includes('deleted file mode')) {
            changeType = 'deleted';
        }

        // Count lines and extract diff content
        let inDiff = false;
        const diffLines = [];

        lines.forEach(line => {
            if (line.startsWith('@@')) {
                inDiff = true;
            }

            if (inDiff) {
                diffLines.push(line);

                if (line.startsWith('+') && !line.startsWith('+++')) {
                    linesAdded++;
                } else if (line.startsWith('-') && !line.startsWith('---')) {
                    linesRemoved++;
                }
            }
        });

        diffContent = diffLines.join('\n');

        // Extract language from file extension
        const language = this.getLanguageFromPath(filePath);

        return {
            path: filePath,
            changeType,
            linesAdded,
            linesRemoved,
            diffContent,
            language,
            id: this.generateFileId(filePath)
        };
    }

    /**
     * Generate a unique ID for a file
     * @param {string} filePath - The file path
     * @returns {string} Unique ID
     */
    generateFileId(filePath) {
        return `file-${filePath.replace(/[^a-zA-Z0-9]/g, '-')}`;
    }

    /**
     * Get programming language from file path
     * @param {string} filePath - The file path
     * @returns {string} Language identifier
     */
    getLanguageFromPath(filePath) {
        const ext = filePath.split('.').pop().toLowerCase();
        const langMap = {
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'py': 'python',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'go': 'go',
            'rs': 'rust',
            'rb': 'ruby',
            'php': 'php',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'md': 'markdown',
            'sh': 'bash',
            'sql': 'sql',
        };
        return langMap[ext] || 'plaintext';
    }

    /**
     * Create file change summary from structured data
     * @param {Object} changeData - Structured change data
     * @returns {string} HTML for file change summary
     */
    createSummary(changeData) {
        const { files } = changeData;

        if (!files || files.length === 0) {
            return this.renderEmptyState();
        }

        const categorized = this.categorizeFiles(files);
        return this.renderSummary(categorized);
    }

    /**
     * Categorize files by change type
     * @param {Array} files - Array of file objects
     * @returns {Object} Categorized files
     */
    categorizeFiles(files) {
        return {
            created: files.filter(f => f.changeType === 'created'),
            modified: files.filter(f => f.changeType === 'modified'),
            deleted: files.filter(f => f.changeType === 'deleted')
        };
    }

    /**
     * Render the complete summary
     * @param {Object} categorized - Categorized files
     * @returns {string} HTML string
     */
    renderSummary(categorized) {
        const totalAdded = this.sumLines(categorized, 'linesAdded');
        const totalRemoved = this.sumLines(categorized, 'linesRemoved');
        const totalFiles = this.countTotalFiles(categorized);

        return `
            <div class="file-change-summary" data-testid="file-change-summary">
                <div class="file-change-header">
                    <h3 class="file-change-title">File Changes Summary</h3>
                    <div class="file-change-stats" data-testid="file-change-stats">
                        <span class="stat-item" data-testid="total-files">
                            <span class="stat-label">Files:</span>
                            <span class="stat-value">${totalFiles}</span>
                        </span>
                        <span class="stat-item added" data-testid="total-added">
                            <span class="stat-label">+</span>
                            <span class="stat-value">${totalAdded}</span>
                        </span>
                        <span class="stat-item deleted" data-testid="total-removed">
                            <span class="stat-label">-</span>
                            <span class="stat-value">${totalRemoved}</span>
                        </span>
                    </div>
                </div>

                <div class="file-change-content">
                    ${this.renderCategory('Created', categorized.created, 'created')}
                    ${this.renderCategory('Modified', categorized.modified, 'modified')}
                    ${this.renderCategory('Deleted', categorized.deleted, 'deleted')}
                </div>
            </div>
        `;
    }

    /**
     * Sum lines from all files in categorized object
     * @param {Object} categorized - Categorized files
     * @param {string} field - Field to sum ('linesAdded' or 'linesRemoved')
     * @returns {number} Total
     */
    sumLines(categorized, field) {
        let total = 0;
        ['created', 'modified', 'deleted'].forEach(category => {
            categorized[category].forEach(file => {
                total += file[field] || 0;
            });
        });
        return total;
    }

    /**
     * Count total files in categorized object
     * @param {Object} categorized - Categorized files
     * @returns {number} Total file count
     */
    countTotalFiles(categorized) {
        return categorized.created.length +
               categorized.modified.length +
               categorized.deleted.length;
    }

    /**
     * Render a category section
     * @param {string} title - Category title
     * @param {Array} files - Files in category
     * @param {string} type - Category type
     * @returns {string} HTML string
     */
    renderCategory(title, files, type) {
        if (files.length === 0) return '';

        return `
            <div class="file-category" data-testid="file-category-${type}">
                <h4 class="category-title">
                    <span class="category-icon category-icon-${type}"></span>
                    ${title} (${files.length})
                </h4>
                <div class="category-files">
                    ${files.map(file => this.renderFile(file, type)).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Render a single file
     * @param {Object} file - File object
     * @param {string} type - Change type
     * @returns {string} HTML string
     */
    renderFile(file, type) {
        const isExpanded = this.expandedFiles.has(file.id);

        return `
            <div class="file-item" data-testid="file-item-${file.id}">
                <div class="file-header"
                     onclick="window.fileChangeSummary.toggleFile('${file.id}')"
                     data-testid="file-header-${file.id}">
                    <div class="file-info">
                        <span class="file-expand-icon ${isExpanded ? 'expanded' : ''}"
                              data-testid="expand-icon-${file.id}">
                            ▶
                        </span>
                        <span class="file-path" data-testid="file-path-${file.id}">${this.escapeHtml(file.path)}</span>
                    </div>
                    <div class="file-stats">
                        ${file.linesAdded > 0 ? `<span class="stat-badge added" data-testid="lines-added-${file.id}">+${file.linesAdded}</span>` : ''}
                        ${file.linesRemoved > 0 ? `<span class="stat-badge deleted" data-testid="lines-removed-${file.id}">-${file.linesRemoved}</span>` : ''}
                    </div>
                </div>
                <div class="file-diff ${isExpanded ? 'expanded' : ''}"
                     id="diff-${file.id}"
                     data-testid="file-diff-${file.id}">
                    ${this.renderDiff(file)}
                </div>
            </div>
        `;
    }

    /**
     * Render diff content for a file
     * @param {Object} file - File object
     * @returns {string} HTML string
     */
    renderDiff(file) {
        if (!file.diffContent || file.diffContent.trim() === '') {
            return '<div class="diff-empty">No diff content available</div>';
        }

        const lines = file.diffContent.split('\n');
        let diffHtml = '';

        lines.forEach(line => {
            if (line.startsWith('@@')) {
                diffHtml += `<div class="diff-line hunk-header" data-testid="diff-line-hunk">${this.escapeHtml(line)}</div>`;
            } else if (line.startsWith('+') && !line.startsWith('+++')) {
                diffHtml += `<div class="diff-line added" data-testid="diff-line-added"><span class="diff-indicator">+</span><code>${this.escapeHtml(line.substring(1))}</code></div>`;
            } else if (line.startsWith('-') && !line.startsWith('---')) {
                diffHtml += `<div class="diff-line deleted" data-testid="diff-line-deleted"><span class="diff-indicator">-</span><code>${this.escapeHtml(line.substring(1))}</code></div>`;
            } else if (!line.startsWith('---') && !line.startsWith('+++')) {
                diffHtml += `<div class="diff-line context" data-testid="diff-line-context"><span class="diff-indicator"> </span><code>${this.escapeHtml(line)}</code></div>`;
            }
        });

        return `<div class="diff-content" data-testid="diff-content">${diffHtml}</div>`;
    }

    /**
     * Toggle file expansion
     * @param {string} fileId - File ID
     */
    toggleFile(fileId) {
        if (this.expandedFiles.has(fileId)) {
            this.expandedFiles.delete(fileId);
        } else {
            this.expandedFiles.add(fileId);
        }

        const diffElement = document.getElementById(`diff-${fileId}`);
        const iconElement = document.querySelector(`[data-testid="expand-icon-${fileId}"]`);

        if (diffElement) {
            diffElement.classList.toggle('expanded');
        }

        if (iconElement) {
            iconElement.classList.toggle('expanded');
        }

        // Apply syntax highlighting after expansion
        if (this.expandedFiles.has(fileId) && typeof hljs !== 'undefined') {
            setTimeout(() => {
                diffElement.querySelectorAll('code').forEach(codeBlock => {
                    hljs.highlightElement(codeBlock);
                });
            }, 0);
        }
    }

    /**
     * Render empty state
     * @returns {string} HTML string
     */
    renderEmptyState() {
        return `
            <div class="file-change-summary empty" data-testid="file-change-summary-empty">
                <div class="empty-state">
                    <p>No file changes to display</p>
                </div>
            </div>
        `;
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }

    /**
     * Reset expanded state
     */
    reset() {
        this.expandedFiles.clear();
    }
}

// Export for Node.js/Jest testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { FileChangeSummary };
}
