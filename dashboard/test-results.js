/**
 * Test Results Component
 * Displays test execution results with pass/fail status and test case details
 * Adapted from reusable/a2ui-components/components/test-results.tsx
 *
 * Features:
 * - Summary statistics (total, passed, failed, skipped)
 * - Progress bar with color coding
 * - Test suites with expand/collapse
 * - Individual test cases with status and error details
 * - Playwright test screenshot evidence support
 */

class TestResults {
    constructor(containerId = 'test-results-container') {
        this.container = document.getElementById(containerId);
        this.expandedTests = new Set();
        this.expandedSuites = new Set();
        this.data = null;
    }

    /**
     * Render test results data
     * @param {Object} testData - Test results data matching TestResultsData interface
     */
    render(testData) {
        if (!this.container) {
            console.error('Test results container not found');
            return;
        }

        this.data = testData;
        this.expandedTests.clear();
        this.expandedSuites.clear();

        const html = this.generateHTML();
        this.container.innerHTML = html;
        this.attachEventListeners();
    }

    /**
     * Generate HTML for test results
     */
    generateHTML() {
        const {
            totalTests = 0,
            passedTests = 0,
            failedTests = 0,
            skippedTests = 0,
            duration,
            testCases = [],
            testSuites = []
        } = this.data;

        const passRate = totalTests > 0 ? Math.round((passedTests / totalTests) * 100) : 0;
        const failRate = totalTests > 0 ? Math.round((failedTests / totalTests) * 100) : 0;

        let html = `
            <div class="test-results" data-testid="test-results">
                <div class="test-results-header">
                    <h3 class="test-results-title">Test Results</h3>
                </div>

                <!-- Summary Section -->
                <div class="test-results-summary" data-testid="test-summary">
                    <div class="test-summary-item total">
                        <div class="test-summary-value">${totalTests}</div>
                        <div class="test-summary-label">Total Tests</div>
                    </div>
                    <div class="test-summary-item passed">
                        <div class="test-summary-value">${passedTests}</div>
                        <div class="test-summary-label">Passed (${passRate}%)</div>
                    </div>
                    <div class="test-summary-item failed">
                        <div class="test-summary-value">${failedTests}</div>
                        <div class="test-summary-label">Failed (${failRate}%)</div>
                    </div>
        `;

        if (skippedTests > 0) {
            html += `
                    <div class="test-summary-item skipped">
                        <div class="test-summary-value">${skippedTests}</div>
                        <div class="test-summary-label">Skipped</div>
                    </div>
            `;
        }

        html += `
                </div>

                <!-- Progress Bar -->
                <div class="test-results-progress" data-testid="progress-bar-container">
                    <div class="test-progress-label-row">
                        <span class="test-progress-label">Pass Rate</span>
                        <span class="test-progress-percentage ${this.getProgressClass(passRate)}">${passRate}%</span>
                    </div>
                    <div class="test-progress-bar">
                        <div
                            class="test-progress-fill ${this.getProgressClass(passRate)}"
                            style="width: ${passRate}%"
                            data-testid="progress-bar"
                        ></div>
                    </div>
                </div>
        `;

        if (duration !== undefined) {
            html += `
                <div class="test-results-duration" data-testid="duration">
                    Total Duration: <span class="test-duration-value">${this.formatDuration(duration)}</span>
                </div>
            `;
        }

        // Test Suites
        if (testSuites.length > 0) {
            html += this.generateSuitesHTML(testSuites);
        }

        // Test Cases
        if (testCases.length > 0) {
            html += this.generateTestCasesHTML(testCases);
        }

        html += '</div>';
        return html;
    }

    /**
     * Generate HTML for test suites
     */
    generateSuitesHTML(testSuites) {
        let html = '<div class="test-suites" data-testid="test-suites"><h4 class="test-suites-title">Test Suites</h4>';

        testSuites.forEach((suite, suiteIndex) => {
            const suiteId = `suite-${suiteIndex}`;
            const suiteTotal = suite.total || 0;
            const suitePassRate = suiteTotal > 0 ? Math.round((suite.passed / suiteTotal) * 100) : 0;
            const isExpanded = this.expandedSuites.has(suiteId);

            html += `
                <div class="test-suite" data-testid="test-suite-${suiteIndex}">
                    <button
                        class="test-suite-header ${isExpanded ? 'expanded' : ''}"
                        data-testid="suite-toggle-${suiteIndex}"
                        data-suite-id="${suiteId}"
                    >
                        <span class="test-suite-chevron">${isExpanded ? '▼' : '▶'}</span>
                        <div class="test-suite-info">
                            <div class="test-suite-name" data-testid="suite-name-${suiteIndex}">${this.escapeHtml(suite.name)}</div>
                            <div class="test-suite-stats">
                                ${suiteTotal} tests • ${suite.passed} passed • ${suite.failed} failed
                                ${(suite.skipped || 0) > 0 ? ` • ${suite.skipped} skipped` : ''}
                            </div>
                        </div>
                        <div class="test-suite-meta">
                            <span class="test-suite-duration">${this.formatDuration(suite.duration)}</span>
                            <span class="test-suite-rate ${this.getProgressClass(suitePassRate)}">${suitePassRate}%</span>
                        </div>
                    </button>

                    ${isExpanded && Array.isArray(suite.tests) ? `
                        <div class="test-suite-tests" data-testid="suite-tests-${suiteIndex}">
                            ${suite.tests.map((test, testIndex) => this.generateTestItemHTML(test, testIndex, `suite-${suiteIndex}-${testIndex}`)).join('')}
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += '</div>';
        return html;
    }

    /**
     * Generate HTML for test cases
     */
    generateTestCasesHTML(testCases) {
        let html = '<div class="test-cases" data-testid="test-case-list"><h4 class="test-cases-title">Test Cases</h4>';

        testCases.forEach((testCase, index) => {
            html += this.generateTestItemHTML(testCase, index, `test-${index}`);
        });

        html += '</div>';
        return html;
    }

    /**
     * Generate HTML for a single test item
     */
    generateTestItemHTML(test, index, testId) {
        const isExpanded = this.expandedTests.has(testId);
        const hasError = test.status === 'failed' && test.error;

        return `
            <div
                class="test-item test-${test.status} ${hasError ? 'has-error' : ''}"
                data-testid="test-case-${index}"
                data-test-id="${testId}"
            >
                <div class="test-item-header ${hasError ? 'clickable' : ''}">
                    <div class="test-item-content">
                        <span class="test-status-badge badge-${test.status}" data-testid="badge-${test.status}">
                            ${this.getStatusIcon(test.status)}
                            ${this.getStatusLabel(test.status)}
                        </span>
                        ${test.duration !== undefined ? `<span class="test-duration" data-testid="test-duration-${index}">${this.formatDuration(test.duration)}</span>` : ''}
                        <div class="test-name" data-testid="test-name-${index}">${this.escapeHtml(test.name)}</div>
                    </div>
                    ${hasError ? `
                        <button class="test-expand-btn" data-test-id="${testId}">
                            ${isExpanded ? '▼' : '▶'}
                        </button>
                    ` : ''}
                </div>
                ${hasError && !isExpanded ? `
                    <div class="test-error-preview" data-testid="error-preview-${index}">
                        ${this.truncateError(test.error, 100)}
                    </div>
                ` : ''}
                ${hasError && isExpanded ? `
                    <div class="test-error-details" data-testid="error-details-${index}">
                        <div class="test-error-label">Error Details:</div>
                        <div class="test-error-content">${this.escapeHtml(test.error)}</div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Attach event listeners to interactive elements
     */
    attachEventListeners() {
        if (!this.container) return;

        // Suite toggle buttons
        this.container.querySelectorAll('.test-suite-header').forEach(btn => {
            btn.addEventListener('click', (e) => this.toggleSuite(e));
        });

        // Test expand buttons
        this.container.querySelectorAll('.test-expand-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.toggleTestDetails(e));
        });

        // Test items with errors (clickable)
        this.container.querySelectorAll('.test-item.has-error .test-item-header.clickable').forEach(header => {
            header.addEventListener('click', (e) => {
                if (!e.target.closest('.test-expand-btn')) {
                    const testId = header.closest('.test-item').dataset.testId;
                    this.toggleTestById(testId);
                }
            });
        });
    }

    /**
     * Toggle suite expansion
     */
    toggleSuite(event) {
        const btn = event.currentTarget;
        const suiteId = btn.dataset.suiteId;

        if (this.expandedSuites.has(suiteId)) {
            this.expandedSuites.delete(suiteId);
            btn.classList.remove('expanded');
        } else {
            this.expandedSuites.add(suiteId);
            btn.classList.add('expanded');
        }

        // Re-render to show/hide suite tests
        this.renderSuiteExpanded(btn, suiteId);
    }

    /**
     * Toggle test details expansion
     */
    toggleTestDetails(event) {
        event.preventDefault();
        const btn = event.currentTarget;
        const testId = btn.dataset.testId;
        this.toggleTestById(testId);
    }

    /**
     * Toggle test by ID
     */
    toggleTestById(testId) {
        const testItem = this.container.querySelector(`[data-test-id="${testId}"]`);
        if (!testItem) return;

        if (this.expandedTests.has(testId)) {
            this.expandedTests.delete(testId);
            testItem.classList.remove('expanded');
            const errorDetails = testItem.querySelector('.test-error-details');
            if (errorDetails) errorDetails.remove();
            const expandBtn = testItem.querySelector('.test-expand-btn');
            if (expandBtn) expandBtn.textContent = '▶';
        } else {
            this.expandedTests.add(testId);
            testItem.classList.add('expanded');
            const errorPreview = testItem.querySelector('.test-error-preview');
            if (errorPreview) errorPreview.remove();

            // Add error details
            const test = this.findTestInData(testId);
            if (test && test.error) {
                const errorDetails = document.createElement('div');
                errorDetails.className = 'test-error-details';
                errorDetails.setAttribute('data-testid', `error-details-${testId}`);
                errorDetails.innerHTML = `
                    <div class="test-error-label">Error Details:</div>
                    <div class="test-error-content">${this.escapeHtml(test.error)}</div>
                `;
                const header = testItem.querySelector('.test-item-header');
                header.parentNode.insertBefore(errorDetails, header.nextSibling);
            }

            const expandBtn = testItem.querySelector('.test-expand-btn');
            if (expandBtn) expandBtn.textContent = '▼';
        }
    }

    /**
     * Render suite expanded state
     */
    renderSuiteExpanded(btn, suiteId) {
        const suite = btn.closest('.test-suite');
        const testsContainer = suite.querySelector('.test-suite-tests');

        if (testsContainer) {
            if (this.expandedSuites.has(suiteId)) {
                testsContainer.style.display = 'block';
            } else {
                testsContainer.style.display = 'none';
            }
        }
    }

    /**
     * Find test in data by ID
     */
    findTestInData(testId) {
        if (!this.data) return null;

        // Check test cases
        const testCases = this.data.testCases || [];
        for (let i = 0; i < testCases.length; i++) {
            if (`test-${i}` === testId) return testCases[i];
        }

        // Check test suites
        const testSuites = this.data.testSuites || [];
        for (let suiteIdx = 0; suiteIdx < testSuites.length; suiteIdx++) {
            const suite = testSuites[suiteIdx];
            if (Array.isArray(suite.tests)) {
                for (let testIdx = 0; testIdx < suite.tests.length; testIdx++) {
                    if (`suite-${suiteIdx}-${testIdx}` === testId) {
                        return suite.tests[testIdx];
                    }
                }
            }
        }

        return null;
    }

    /**
     * Get progress bar CSS class
     */
    getProgressClass(passRate) {
        if (passRate >= 80) return 'progress-success';
        if (passRate >= 50) return 'progress-warning';
        return 'progress-error';
    }

    /**
     * Get status icon
     */
    getStatusIcon(status) {
        const icons = {
            passed: '✓',
            failed: '✕',
            skipped: '⊘',
            running: '⟳'
        };
        return icons[status] || '•';
    }

    /**
     * Get status label
     */
    getStatusLabel(status) {
        const labels = {
            passed: 'Passed',
            failed: 'Failed',
            skipped: 'Skipped',
            running: 'Running'
        };
        return labels[status] || 'Unknown';
    }

    /**
     * Format duration
     */
    formatDuration(seconds) {
        if (seconds === undefined) return '';
        if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
        return `${seconds.toFixed(2)}s`;
    }

    /**
     * Truncate error message
     */
    truncateError(error, maxLength = 100) {
        if (error.length <= maxLength) return error;
        return error.substring(0, maxLength) + '...';
    }

    /**
     * Escape HTML
     */
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

    /**
     * Get test results data
     */
    getTestResults() {
        return this.data;
    }

    /**
     * Clear test results
     */
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.data = null;
        this.expandedTests.clear();
        this.expandedSuites.clear();
    }
}

// Make TestResults available globally
if (typeof window !== 'undefined') {
    window.TestResults = TestResults;
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TestResults;
}
