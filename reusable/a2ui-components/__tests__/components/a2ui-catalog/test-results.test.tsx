import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TestResults } from '@/components/a2ui-catalog/test-results';
import { A2UIProps, TestResultsData, TestSuite, A2UIEventType } from '@/lib/a2ui-types';

describe('TestResults Component', () => {
  const mockOnEvent = jest.fn();

  const createProps = (data: Partial<TestResultsData>): A2UIProps => ({
    type: 'a2ui.TestResults',
    data: {
      testId: 'test-1',
      title: 'Test Results',
      status: 'passed',
      totalTests: 0,
      passedTests: 0,
      failedTests: 0,
      ...data,
    },
    metadata: { componentId: 'test-results-1' },
    onEvent: mockOnEvent,
  });

  beforeEach(() => {
    mockOnEvent.mockClear();
  });

  describe('Summary Section', () => {
    test('renders with basic test summary', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 8,
        failedTests: 2,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('test-results')).toBeInTheDocument();
      expect(screen.getByText('Test Results')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    test('displays correct pass percentage', () => {
      const data: TestResultsData = {
        totalTests: 100,
        passedTests: 75,
        failedTests: 25,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('Passed (75%)')).toBeInTheDocument();
      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    test('displays correct fail percentage', () => {
      const data: TestResultsData = {
        totalTests: 50,
        passedTests: 40,
        failedTests: 10,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('Failed (20%)')).toBeInTheDocument();
    });

    test('handles zero tests correctly', () => {
      const data: TestResultsData = {
        totalTests: 0,
        passedTests: 0,
        failedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('0%')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar')).toHaveStyle({ width: '0%' });
    });

    test('displays skipped tests when provided', () => {
      const data: TestResultsData = {
        totalTests: 20,
        passedTests: 15,
        failedTests: 2,
        skippedTests: 3,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('Skipped')).toBeInTheDocument();
    });

    test('does not display skipped tests section when zero', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 8,
        failedTests: 2,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByText('Skipped')).not.toBeInTheDocument();
    });

    test('displays duration when provided', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        duration: 5.25,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('duration')).toBeInTheDocument();
      expect(screen.getByText('5.25s')).toBeInTheDocument();
    });

    test('formats duration in milliseconds for values < 1 second', () => {
      const data: TestResultsData = {
        totalTests: 5,
        passedTests: 5,
        failedTests: 0,
        duration: 0.123,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('123ms')).toBeInTheDocument();
    });

    test('does not display duration when not provided', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByTestId('duration')).not.toBeInTheDocument();
    });
  });

  describe('Progress Bar', () => {
    test('shows green color for pass rate >= 80%', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 9,
        failedTests: 1,
      };

      render(<TestResults {...createProps(data)} />);

      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveClass('bg-green-400');
    });

    test('shows orange color for pass rate between 50-79%', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 7,
        failedTests: 3,
      };

      render(<TestResults {...createProps(data)} />);

      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveClass('bg-orange-400');
    });

    test('shows red color for pass rate < 50%', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 4,
        failedTests: 6,
      };

      render(<TestResults {...createProps(data)} />);

      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveClass('bg-red-400');
    });

    test('progress bar width matches pass rate', () => {
      const data: TestResultsData = {
        totalTests: 100,
        passedTests: 65,
        failedTests: 35,
      };

      render(<TestResults {...createProps(data)} />);

      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveStyle({ width: '65%' });
    });
  });

  describe('Test Case List', () => {
    test('displays test case list when provided', () => {
      const data: TestResultsData = {
        totalTests: 3,
        passedTests: 2,
        failedTests: 1,
        testCases: [
          { name: 'Test 1', status: 'passed', duration: 0.5 },
          { name: 'Test 2', status: 'failed', duration: 1.2, error: 'Assertion failed' },
          { name: 'Test 3', status: 'passed', duration: 0.8 },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('test-case-list')).toBeInTheDocument();
      expect(screen.getByText('Test Cases')).toBeInTheDocument();
      expect(screen.getByTestId('test-case-0')).toBeInTheDocument();
      expect(screen.getByTestId('test-case-1')).toBeInTheDocument();
      expect(screen.getByTestId('test-case-2')).toBeInTheDocument();
    });

    test('does not display test case list when empty', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        testCases: [],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByTestId('test-case-list')).not.toBeInTheDocument();
    });

    test('displays test case names correctly', () => {
      const data: TestResultsData = {
        totalTests: 2,
        passedTests: 2,
        failedTests: 0,
        testCases: [
          { name: 'should render component', status: 'passed' },
          { name: 'should handle click events', status: 'passed' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('should render component')).toBeInTheDocument();
      expect(screen.getByText('should handle click events')).toBeInTheDocument();
    });

    test('displays test duration for each test case', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 1,
        failedTests: 0,
        testCases: [
          { name: 'Test with duration', status: 'passed', duration: 2.5 },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('test-duration-0')).toHaveTextContent('2.50s');
    });

    test('displays passed test with correct icon and badge', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 1,
        failedTests: 0,
        testCases: [
          { name: 'Passed test', status: 'passed' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const testCase = screen.getByTestId('test-case-0');
      expect(within(testCase).getByTestId('badge-passed')).toBeInTheDocument();
      expect(within(testCase).getByTestId('icon-passed')).toBeInTheDocument();
      expect(within(testCase).getByText('Passed')).toBeInTheDocument();
    });

    test('displays failed test with correct icon and badge', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 1,
        testCases: [
          { name: 'Failed test', status: 'failed', error: 'Error message' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('badge-failed')).toBeInTheDocument();
      expect(screen.getByTestId('icon-failed')).toBeInTheDocument();
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });

    test('displays skipped test with correct icon and badge', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 1,
        testCases: [
          { name: 'Skipped test', status: 'skipped' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('badge-skipped')).toBeInTheDocument();
      expect(screen.getByTestId('icon-skipped')).toBeInTheDocument();
      // Use getAllByText since "Skipped" appears in both summary and badge
      const skippedTexts = screen.getAllByText('Skipped');
      expect(skippedTexts.length).toBeGreaterThan(0);
    });
  });

  describe('Error Handling and Expansion', () => {
    test('displays error preview for failed tests', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 1,
        testCases: [
          { name: 'Failed test', status: 'failed', error: 'Assertion failed: expected true but got false' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('error-preview-0')).toBeInTheDocument();
      expect(screen.getByText(/Assertion failed/)).toBeInTheDocument();
    });

    test('truncates long error messages with ellipsis', () => {
      const longError = 'A'.repeat(150);
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 1,
        testCases: [
          { name: 'Failed test', status: 'failed', error: longError },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const preview = screen.getByTestId('error-preview-0');
      expect(preview.textContent).toContain('...');
      expect(preview.textContent!.length).toBeLessThan(longError.length);
    });

    test('expands error details when clicked', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 1,
        testCases: [
          { name: 'Failed test', status: 'failed', error: 'Full error message here' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      // Initially error details should not be visible
      expect(screen.queryByTestId('error-details-0')).not.toBeInTheDocument();

      // Click to expand
      const testCase = screen.getByTestId('test-case-0');
      fireEvent.click(testCase);

      // Error details should now be visible
      expect(screen.getByTestId('error-details-0')).toBeInTheDocument();
      expect(screen.getByText('Full error message here')).toBeInTheDocument();
    });

    test('collapses error details when clicked again', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 1,
        testCases: [
          { name: 'Failed test', status: 'failed', error: 'Error message' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const testCase = screen.getByTestId('test-case-0');

      // Expand
      fireEvent.click(testCase);
      expect(screen.getByTestId('error-details-0')).toBeInTheDocument();

      // Collapse
      fireEvent.click(testCase);
      expect(screen.queryByTestId('error-details-0')).not.toBeInTheDocument();
    });

    test('shows expand button for failed tests with errors', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 1,
        testCases: [
          { name: 'Failed test', status: 'failed', error: 'Error' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('expand-button-0')).toBeInTheDocument();
    });

    test('does not show expand button for passed tests', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 1,
        failedTests: 0,
        testCases: [
          { name: 'Passed test', status: 'passed' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByTestId('expand-button-0')).not.toBeInTheDocument();
    });

    test('does not show expand button for failed tests without errors', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 1,
        testCases: [
          { name: 'Failed test', status: 'failed' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByTestId('expand-button-0')).not.toBeInTheDocument();
    });

    test('emits click event when expanding error details', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 1,
        testCases: [
          { name: 'Failed test', status: 'failed', error: 'Error' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const testCase = screen.getByTestId('test-case-0');
      fireEvent.click(testCase);

      expect(mockOnEvent).toHaveBeenCalledWith(
        A2UIEventType.CLICK,
        expect.objectContaining({
          action: 'toggle_test_details',
          testIndex: 0,
          expanded: true,
        })
      );
    });

    test('emits click event when collapsing error details', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 1,
        testCases: [
          { name: 'Failed test', status: 'failed', error: 'Error' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const testCase = screen.getByTestId('test-case-0');

      // Expand first
      fireEvent.click(testCase);
      mockOnEvent.mockClear();

      // Then collapse
      fireEvent.click(testCase);

      expect(mockOnEvent).toHaveBeenCalledWith(
        A2UIEventType.CLICK,
        expect.objectContaining({
          action: 'toggle_test_details',
          testIndex: 0,
          expanded: false,
        })
      );
    });
  });

  describe('Edge Cases', () => {
    test('handles all tests passed scenario', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('100%')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar')).toHaveClass('bg-green-400');
    });

    test('handles all tests failed scenario', () => {
      const data: TestResultsData = {
        totalTests: 5,
        passedTests: 0,
        failedTests: 5,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('0%')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar')).toHaveClass('bg-red-400');
    });

    test('handles all tests skipped scenario', () => {
      const data: TestResultsData = {
        totalTests: 5,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 5,
      };

      render(<TestResults {...createProps(data)} />);

      const summary = screen.getByTestId('test-summary');
      expect(within(summary).getAllByText('5')).toHaveLength(2); // Total and skipped
      expect(within(summary).getByText('Skipped')).toBeInTheDocument();
    });

    test('handles missing optional fields gracefully', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 8,
        failedTests: 2,
        // No skippedTests, duration, or testCases
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('test-results')).toBeInTheDocument();
      expect(screen.queryByText('Skipped')).not.toBeInTheDocument();
      expect(screen.queryByTestId('duration')).not.toBeInTheDocument();
      expect(screen.queryByTestId('test-case-list')).not.toBeInTheDocument();
    });

    test('handles test case without duration', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 1,
        failedTests: 0,
        testCases: [
          { name: 'Test without duration', status: 'passed' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByTestId('test-duration-0')).not.toBeInTheDocument();
    });

    test('handles multiple expanded tests simultaneously', () => {
      const data: TestResultsData = {
        totalTests: 3,
        passedTests: 0,
        failedTests: 3,
        testCases: [
          { name: 'Failed 1', status: 'failed', error: 'Error 1' },
          { name: 'Failed 2', status: 'failed', error: 'Error 2' },
          { name: 'Failed 3', status: 'failed', error: 'Error 3' },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      // Expand all three
      fireEvent.click(screen.getByTestId('test-case-0'));
      fireEvent.click(screen.getByTestId('test-case-1'));
      fireEvent.click(screen.getByTestId('test-case-2'));

      // All should be expanded
      expect(screen.getByTestId('error-details-0')).toBeInTheDocument();
      expect(screen.getByTestId('error-details-1')).toBeInTheDocument();
      expect(screen.getByTestId('error-details-2')).toBeInTheDocument();
    });

    test('applies dark theme classes', () => {
      const data: TestResultsData = {
        totalTests: 5,
        passedTests: 5,
        failedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      const container = screen.getByTestId('test-results');
      expect(container).toHaveClass('bg-gray-900');
      expect(container).toHaveClass('border-gray-800');
      expect(container).toHaveClass('text-gray-100');
    });
  });

  describe('Test Suites', () => {
    test('renders test suites when provided', () => {
      const data: TestResultsData = {
        totalTests: 6,
        passedTests: 5,
        failedTests: 1,
        testSuites: [
          {
            name: 'Component Tests',
            total: 3,
            passed: 3,
            failed: 0,
            skipped: 0,
            duration: 1.5,
            tests: [
              { name: 'renders correctly', status: 'passed', duration: 0.5 },
              { name: 'handles props', status: 'passed', duration: 0.4 },
              { name: 'updates on change', status: 'passed', duration: 0.6 },
            ],
          },
          {
            name: 'Integration Tests',
            total: 3,
            passed: 2,
            failed: 1,
            skipped: 0,
            duration: 2.3,
            tests: [
              { name: 'API integration', status: 'passed', duration: 1.2 },
              { name: 'Database query', status: 'failed', duration: 0.8, error: 'Connection timeout' },
              { name: 'Cache invalidation', status: 'passed', duration: 0.3 },
            ],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('test-suites')).toBeInTheDocument();
      expect(screen.getByTestId('test-suite-0')).toBeInTheDocument();
      expect(screen.getByTestId('test-suite-1')).toBeInTheDocument();
    });

    test('displays suite names correctly', () => {
      const data: TestResultsData = {
        totalTests: 3,
        passedTests: 3,
        failedTests: 0,
        testSuites: [
          {
            name: 'Unit Tests',
            total: 3,
            passed: 3,
            failed: 0,
            skipped: 0,
            duration: 1.0,
            tests: [],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('suite-name-0')).toHaveTextContent('Unit Tests');
    });

    test('displays suite statistics', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 7,
        failedTests: 2,
        skippedTests: 1,
        testSuites: [
          {
            name: 'Integration Tests',
            total: 10,
            passed: 7,
            failed: 2,
            skipped: 1,
            duration: 5.5,
            tests: [],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const suite = screen.getByTestId('test-suite-0');
      expect(within(suite).getByText(/10 tests/)).toBeInTheDocument();
      expect(within(suite).getByText(/7 passed/)).toBeInTheDocument();
      expect(within(suite).getByText(/2 failed/)).toBeInTheDocument();
      expect(within(suite).getByText(/1 skipped/)).toBeInTheDocument();
    });

    test('suites start collapsed by default', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 1,
        failedTests: 0,
        testSuites: [
          {
            name: 'Test Suite',
            total: 1,
            passed: 1,
            failed: 0,
            skipped: 0,
            duration: 1.0,
            tests: [
              { name: 'Test 1', status: 'passed' },
            ],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByTestId('suite-tests-0')).not.toBeInTheDocument();
    });

    test('expands suite when header clicked', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 1,
        failedTests: 0,
        testSuites: [
          {
            name: 'Test Suite',
            total: 1,
            passed: 1,
            failed: 0,
            skipped: 0,
            duration: 1.0,
            tests: [
              { name: 'Test 1', status: 'passed' },
            ],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const toggle = screen.getByTestId('suite-toggle-0');
      fireEvent.click(toggle);

      expect(screen.getByTestId('suite-tests-0')).toBeInTheDocument();
    });

    test('collapses suite when header clicked again', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 1,
        failedTests: 0,
        testSuites: [
          {
            name: 'Test Suite',
            total: 1,
            passed: 1,
            failed: 0,
            skipped: 0,
            duration: 1.0,
            tests: [
              { name: 'Test 1', status: 'passed' },
            ],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      // Expand
      fireEvent.click(screen.getByTestId('suite-toggle-0'));
      expect(screen.getByTestId('suite-tests-0')).toBeInTheDocument();

      // Collapse - re-query the toggle after DOM update
      fireEvent.click(screen.getByTestId('suite-toggle-0'));
      expect(screen.queryByTestId('suite-tests-0')).not.toBeInTheDocument();
    });

    test('displays tests within expanded suite', () => {
      const data: TestResultsData = {
        totalTests: 2,
        passedTests: 2,
        failedTests: 0,
        testSuites: [
          {
            name: 'Test Suite',
            total: 2,
            passed: 2,
            failed: 0,
            skipped: 0,
            duration: 1.0,
            tests: [
              { name: 'Test A', status: 'passed' },
              { name: 'Test B', status: 'passed' },
            ],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      fireEvent.click(screen.getByTestId('suite-toggle-0'));

      expect(screen.getByTestId('suite-test-0-0')).toBeInTheDocument();
      expect(screen.getByTestId('suite-test-0-1')).toBeInTheDocument();
      expect(screen.getByText('Test A')).toBeInTheDocument();
      expect(screen.getByText('Test B')).toBeInTheDocument();
    });

    test('calculates suite pass rate correctly', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 8,
        failedTests: 2,
        testSuites: [
          {
            name: 'Test Suite',
            total: 10,
            passed: 8,
            failed: 2,
            skipped: 0,
            duration: 1.0,
            tests: [],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const suite = screen.getByTestId('test-suite-0');
      expect(within(suite).getByText('80%')).toBeInTheDocument();
    });

    test('shows green color for suite with >= 80% pass rate', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 9,
        failedTests: 1,
        testSuites: [
          {
            name: 'Test Suite',
            total: 10,
            passed: 9,
            failed: 1,
            skipped: 0,
            duration: 1.0,
            tests: [],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const suite = screen.getByTestId('test-suite-0');
      const passRate = within(suite).getByText('90%');
      expect(passRate).toHaveClass('text-green-400');
    });

    test('shows orange color for suite with 50-79% pass rate', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 6,
        failedTests: 4,
        testSuites: [
          {
            name: 'Test Suite',
            total: 10,
            passed: 6,
            failed: 4,
            skipped: 0,
            duration: 1.0,
            tests: [],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const suite = screen.getByTestId('test-suite-0');
      const passRate = within(suite).getByText('60%');
      expect(passRate).toHaveClass('text-orange-400');
    });

    test('shows red color for suite with < 50% pass rate', () => {
      const data: TestResultsData = {
        totalTests: 10,
        passedTests: 3,
        failedTests: 7,
        testSuites: [
          {
            name: 'Test Suite',
            total: 10,
            passed: 3,
            failed: 7,
            skipped: 0,
            duration: 1.0,
            tests: [],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const suite = screen.getByTestId('test-suite-0');
      const passRate = within(suite).getByText('30%');
      expect(passRate).toHaveClass('text-red-400');
    });

    test('emits event when suite is toggled', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 1,
        failedTests: 0,
        testSuites: [
          {
            name: 'Test Suite',
            total: 1,
            passed: 1,
            failed: 0,
            skipped: 0,
            duration: 1.0,
            tests: [{ name: 'Test', status: 'passed' }],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      fireEvent.click(screen.getByTestId('suite-toggle-0'));

      expect(mockOnEvent).toHaveBeenCalledWith(
        A2UIEventType.CLICK,
        expect.objectContaining({
          action: 'toggle_suite',
          suiteName: 'Test Suite',
          expanded: true,
        })
      );
    });

    test('handles multiple suites expanded simultaneously', () => {
      const data: TestResultsData = {
        totalTests: 4,
        passedTests: 4,
        failedTests: 0,
        testSuites: [
          {
            name: 'Suite 1',
            total: 2,
            passed: 2,
            failed: 0,
            skipped: 0,
            duration: 1.0,
            tests: [
              { name: 'Test 1', status: 'passed' },
              { name: 'Test 2', status: 'passed' },
            ],
          },
          {
            name: 'Suite 2',
            total: 2,
            passed: 2,
            failed: 0,
            skipped: 0,
            duration: 1.5,
            tests: [
              { name: 'Test 3', status: 'passed' },
              { name: 'Test 4', status: 'passed' },
            ],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      fireEvent.click(screen.getByTestId('suite-toggle-0'));
      fireEvent.click(screen.getByTestId('suite-toggle-1'));

      expect(screen.getByTestId('suite-tests-0')).toBeInTheDocument();
      expect(screen.getByTestId('suite-tests-1')).toBeInTheDocument();
    });

    test('displays suite duration', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 1,
        failedTests: 0,
        testSuites: [
          {
            name: 'Test Suite',
            total: 1,
            passed: 1,
            failed: 0,
            skipped: 0,
            duration: 3.25,
            tests: [],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const suite = screen.getByTestId('test-suite-0');
      expect(within(suite).getByText('3.25s')).toBeInTheDocument();
    });

    test('does not render test suites section when empty', () => {
      const data: TestResultsData = {
        totalTests: 5,
        passedTests: 5,
        failedTests: 0,
        testSuites: [],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByTestId('test-suites')).not.toBeInTheDocument();
    });

    test('handles running status in suite tests', () => {
      const data: TestResultsData = {
        totalTests: 1,
        passedTests: 0,
        failedTests: 0,
        testSuites: [
          {
            name: 'Test Suite',
            total: 1,
            passed: 0,
            failed: 0,
            skipped: 0,
            duration: 0,
            tests: [
              { name: 'Currently Running Test', status: 'running' },
            ],
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      fireEvent.click(screen.getByTestId('suite-toggle-0'));

      expect(screen.getByTestId('badge-running')).toBeInTheDocument();
      expect(screen.getByTestId('icon-running')).toBeInTheDocument();
    });
  });
});
