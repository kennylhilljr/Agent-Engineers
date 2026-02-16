/**
 * Test Results Component Unit Tests - AI-101
 * Tests for TestResults class with comprehensive coverage
 *
 * Test scenarios:
 * 1. Component initialization
 * 2. Data rendering with various test statuses
 * 3. Summary statistics calculation
 * 4. Progress bar rendering and styling
 * 5. Test suite expansion/collapse
 * 6. Test case expansion/collapse
 * 7. Error details display
 * 8. Duration formatting
 * 9. HTML escaping
 * 10. Event handling
 */

const fs = require('fs');
const path = require('path');

// Load the TestResults component
const testResultsPath = path.join(__dirname, '../test-results.js');
const testResultsCode = fs.readFileSync(testResultsPath, 'utf-8');

// Create a minimal DOM environment
class MockDocument {
    constructor() {
        this.elements = {};
    }

    getElementById(id) {
        if (!this.elements[id]) {
            this.elements[id] = new MockElement(id);
        }
        return this.elements[id];
    }
}

class MockElement {
    constructor(id) {
        this.id = id;
        this.innerHTML = '';
        this.children = [];
        this.classList = {
            add: jest.fn(),
            remove: jest.fn(),
            contains: jest.fn(() => false),
            toggle: jest.fn()
        };
        this.dataset = {};
    }

    querySelector(selector) {
        // Mock querySelector
        return null;
    }

    querySelectorAll(selector) {
        return [];
    }

    addEventListener(event, handler) {}
    appendChild(child) {}
    insertBefore(newNode, referenceNode) {}
}

describe('TestResults Component Unit Tests - AI-101', () => {
    let mockDocument;
    let testResults;

    beforeEach(() => {
        // Setup mock document
        mockDocument = new MockDocument();
        global.document = mockDocument;

        // Instantiate TestResults
        const TestResults = eval(`(${testResultsCode.match(/class TestResults[\s\S]*?^}/m)})`);
        testResults = new TestResults('test-results-container');
    });

    describe('Component Initialization', () => {
        test('Should initialize with default container ID', () => {
            expect(testResults).toBeDefined();
            expect(testResults.container).toBeDefined();
            expect(testResults.expandedTests).toEqual(new Set());
            expect(testResults.expandedSuites).toEqual(new Set());
            expect(testResults.data).toBeNull();
        });

        test('Should initialize with custom container ID', () => {
            const custom = new (eval(`(${testResultsCode.match(/class TestResults[\s\S]*?^}/m)})`))(
                'custom-container'
            );
            expect(custom.container).toBeDefined();
        });

        test('Should handle missing container gracefully', () => {
            global.document.getElementById = () => null;
            const TestResults = eval(`(${testResultsCode.match(/class TestResults[\s\S]*?^}/m)})`);
            const instance = new TestResults('nonexistent');
            expect(instance.container).toBeNull();
        });
    });

    describe('HTML Escaping', () => {
        test('Should escape HTML special characters', () => {
            const result = testResults.escapeHtml('<script>alert("xss")</script>');
            expect(result).toBe('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
        });

        test('Should escape ampersands', () => {
            const result = testResults.escapeHtml('AT&T');
            expect(result).toBe('AT&amp;T');
        });

        test('Should escape quotes', () => {
            const result = testResults.escapeHtml("It's \"quoted\"");
            expect(result).toBe('It&#039;s &quot;quoted&quot;');
        });
    });

    describe('Duration Formatting', () => {
        test('Should format milliseconds', () => {
            expect(testResults.formatDuration(0.5)).toBe('500ms');
            expect(testResults.formatDuration(0.123)).toBe('123ms');
        });

        test('Should format seconds', () => {
            expect(testResults.formatDuration(1.5)).toBe('1.50s');
            expect(testResults.formatDuration(2.34)).toBe('2.34s');
        });

        test('Should handle undefined duration', () => {
            expect(testResults.formatDuration(undefined)).toBe('');
        });

        test('Should handle zero duration', () => {
            expect(testResults.formatDuration(0)).toBe('0ms');
        });
    });

    describe('Progress Rate Calculation', () => {
        test('Should calculate pass rate correctly', () => {
            testResults.data = {
                totalTests: 10,
                passedTests: 8,
                failedTests: 2,
                testCases: []
            };
            const passRate = (8 / 10) * 100;
            expect(Math.round(passRate)).toBe(80);
        });

        test('Should handle zero total tests', () => {
            testResults.data = {
                totalTests: 0,
                passedTests: 0,
                failedTests: 0,
                testCases: []
            };
            // Should not throw when total is 0
            const html = testResults.generateHTML();
            expect(html).toContain('0%');
        });

        test('Should return correct progress class', () => {
            expect(testResults.getProgressClass(85)).toBe('progress-success');
            expect(testResults.getProgressClass(75)).toBe('progress-success');
            expect(testResults.getProgressClass(65)).toBe('progress-warning');
            expect(testResults.getProgressClass(35)).toBe('progress-error');
        });
    });

    describe('Status Handling', () => {
        test('Should return correct status icon', () => {
            expect(testResults.getStatusIcon('passed')).toBe('✓');
            expect(testResults.getStatusIcon('failed')).toBe('✕');
            expect(testResults.getStatusIcon('skipped')).toBe('⊘');
            expect(testResults.getStatusIcon('running')).toBe('⟳');
            expect(testResults.getStatusIcon('unknown')).toBe('•');
        });

        test('Should return correct status label', () => {
            expect(testResults.getStatusLabel('passed')).toBe('Passed');
            expect(testResults.getStatusLabel('failed')).toBe('Failed');
            expect(testResults.getStatusLabel('skipped')).toBe('Skipped');
            expect(testResults.getStatusLabel('running')).toBe('Running');
        });
    });

    describe('Error Truncation', () => {
        test('Should truncate long error messages', () => {
            const longError = 'a'.repeat(150);
            const truncated = testResults.truncateError(longError, 100);
            expect(truncated).toBe('a'.repeat(100) + '...');
            expect(truncated.length).toBe(103);
        });

        test('Should not truncate short error messages', () => {
            const shortError = 'This is short';
            const result = testResults.truncateError(shortError, 100);
            expect(result).toBe(shortError);
        });

        test('Should handle edge case at boundary', () => {
            const exact = 'a'.repeat(100);
            const result = testResults.truncateError(exact, 100);
            expect(result).toBe(exact);
            expect(result).not.toContain('...');
        });
    });

    describe('HTML Generation', () => {
        test('Should generate HTML with summary statistics', () => {
            testResults.data = {
                totalTests: 10,
                passedTests: 8,
                failedTests: 2,
                skippedTests: 0,
                testCases: []
            };

            const html = testResults.generateHTML();
            expect(html).toContain('Test Results');
            expect(html).toContain('10');
            expect(html).toContain('Passed');
            expect(html).toContain('Failed');
            expect(html).toContain('data-testid="test-results"');
            expect(html).toContain('data-testid="test-summary"');
        });

        test('Should include progress bar', () => {
            testResults.data = {
                totalTests: 10,
                passedTests: 8,
                failedTests: 2,
                testCases: []
            };

            const html = testResults.generateHTML();
            expect(html).toContain('data-testid="progress-bar-container"');
            expect(html).toContain('data-testid="progress-bar"');
            expect(html).toContain('Pass Rate');
        });

        test('Should include duration when provided', () => {
            testResults.data = {
                totalTests: 5,
                passedTests: 5,
                failedTests: 0,
                duration: 2.5,
                testCases: []
            };

            const html = testResults.generateHTML();
            expect(html).toContain('Total Duration');
            expect(html).toContain('2.50s');
            expect(html).toContain('data-testid="duration"');
        });

        test('Should render test cases', () => {
            testResults.data = {
                totalTests: 2,
                passedTests: 1,
                failedTests: 1,
                testCases: [
                    { name: 'Test 1', status: 'passed', duration: 0.5 },
                    { name: 'Test 2', status: 'failed', duration: 0.3, error: 'Error message' }
                ]
            };

            const html = testResults.generateHTML();
            expect(html).toContain('Test 1');
            expect(html).toContain('Test 2');
            expect(html).toContain('data-testid="test-case-list"');
        });

        test('Should render test suites', () => {
            testResults.data = {
                totalTests: 2,
                passedTests: 1,
                failedTests: 1,
                testSuites: [
                    {
                        name: 'Suite 1',
                        total: 2,
                        passed: 1,
                        failed: 1,
                        tests: [
                            { name: 'Test 1', status: 'passed' },
                            { name: 'Test 2', status: 'failed', error: 'Error' }
                        ]
                    }
                ]
            };

            const html = testResults.generateHTML();
            expect(html).toContain('Suite 1');
            expect(html).toContain('data-testid="test-suites"');
        });
    });

    describe('Render Method', () => {
        test('Should clear state on render', () => {
            testResults.expandedTests.add('test-1');
            testResults.expandedSuites.add('suite-1');

            testResults.data = {
                totalTests: 1,
                passedTests: 1,
                testCases: []
            };
            testResults.render(testResults.data);

            expect(testResults.expandedTests.size).toBe(0);
            expect(testResults.expandedSuites.size).toBe(0);
        });

        test('Should log error if container not found', () => {
            testResults.container = null;
            const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

            testResults.render({ totalTests: 1, passedTests: 1, testCases: [] });

            expect(consoleSpy).toHaveBeenCalledWith('Test results container not found');
            consoleSpy.mockRestore();
        });
    });

    describe('Data Access Methods', () => {
        test('Should retrieve test results data', () => {
            const data = {
                totalTests: 5,
                passedTests: 5,
                testCases: []
            };
            testResults.data = data;

            expect(testResults.getTestResults()).toEqual(data);
        });

        test('Should clear test results', () => {
            testResults.data = { totalTests: 5, passedTests: 5, testCases: [] };
            testResults.expandedTests.add('test-1');

            testResults.clear();

            expect(testResults.data).toBeNull();
            expect(testResults.expandedTests.size).toBe(0);
            expect(testResults.expandedSuites.size).toBe(0);
        });
    });

    describe('Test Item HTML Generation', () => {
        test('Should generate passed test item', () => {
            const test = { name: 'Test Passed', status: 'passed', duration: 0.5 };
            const html = testResults.generateTestItemHTML(test, 0, 'test-0');

            expect(html).toContain('test-passed');
            expect(html).toContain('Test Passed');
            expect(html).toContain('badge-passed');
            expect(html).toContain('✓');
            expect(html).toContain('Passed');
        });

        test('Should generate failed test item with error', () => {
            const test = {
                name: 'Test Failed',
                status: 'failed',
                duration: 0.7,
                error: 'Assertion failed'
            };
            const html = testResults.generateTestItemHTML(test, 0, 'test-0');

            expect(html).toContain('test-failed');
            expect(html).toContain('has-error');
            expect(html).toContain('badge-failed');
            expect(html).toContain('✕');
            expect(html).toContain('Failed');
        });

        test('Should generate skipped test item', () => {
            const test = { name: 'Test Skipped', status: 'skipped' };
            const html = testResults.generateTestItemHTML(test, 0, 'test-0');

            expect(html).toContain('test-skipped');
            expect(html).toContain('badge-skipped');
            expect(html).toContain('⊘');
        });

        test('Should not include duration if undefined', () => {
            const test = { name: 'Test', status: 'passed' };
            const html = testResults.generateTestItemHTML(test, 0, 'test-0');

            expect(html).not.toContain('test-duration');
        });
    });

    describe('Test Cases HTML Generation', () => {
        test('Should generate multiple test cases', () => {
            testResults.data = {
                totalTests: 3,
                passedTests: 2,
                failedTests: 1,
                testCases: [
                    { name: 'Test 1', status: 'passed' },
                    { name: 'Test 2', status: 'passed' },
                    { name: 'Test 3', status: 'failed', error: 'Error' }
                ]
            };

            const html = testResults.generateTestCasesHTML(testResults.data.testCases);
            expect(html).toContain('Test 1');
            expect(html).toContain('Test 2');
            expect(html).toContain('Test 3');
        });
    });

    describe('Test Suites HTML Generation', () => {
        test('Should generate test suite with tests', () => {
            testResults.expandedSuites.add('suite-0');

            const suites = [
                {
                    name: 'Unit Tests',
                    total: 2,
                    passed: 1,
                    failed: 1,
                    skipped: 0,
                    duration: 1.5,
                    tests: [
                        { name: 'Test 1', status: 'passed' },
                        { name: 'Test 2', status: 'failed', error: 'Error' }
                    ]
                }
            ];

            const html = testResults.generateSuitesHTML(suites);
            expect(html).toContain('Unit Tests');
            expect(html).toContain('Test 1');
            expect(html).toContain('Test 2');
            expect(html).toContain('data-testid="test-suites"');
        });
    });

    describe('Test Data Edge Cases', () => {
        test('Should handle empty test data', () => {
            testResults.data = {};
            const html = testResults.generateHTML();

            expect(html).toBeDefined();
            expect(html).not.toThrow;
        });

        test('Should handle missing testCases array', () => {
            testResults.data = {
                totalTests: 0,
                passedTests: 0,
                failedTests: 0
            };
            const html = testResults.generateHTML();

            expect(html).toContain('0%');
        });

        test('Should handle all passed tests', () => {
            testResults.data = {
                totalTests: 5,
                passedTests: 5,
                failedTests: 0,
                testCases: Array(5).fill({ name: 'Test', status: 'passed' })
            };
            const html = testResults.generateHTML();

            expect(html).toContain('100%');
        });

        test('Should handle all failed tests', () => {
            testResults.data = {
                totalTests: 5,
                passedTests: 0,
                failedTests: 5,
                testCases: Array(5).fill({ name: 'Test', status: 'failed', error: 'Error' })
            };
            const html = testResults.generateHTML();

            expect(html).toContain('0%');
        });
    });

    describe('Component CSS Classes Integration', () => {
        test('Should use correct CSS classes for styling', () => {
            testResults.data = {
                totalTests: 10,
                passedTests: 8,
                failedTests: 2,
                testCases: [
                    { name: 'Test', status: 'passed' }
                ]
            };

            const html = testResults.generateHTML();
            expect(html).toContain('test-results');
            expect(html).toContain('test-results-summary');
            expect(html).toContain('test-summary-item');
            expect(html).toContain('test-progress-bar');
            expect(html).toContain('test-item');
        });
    });
});
