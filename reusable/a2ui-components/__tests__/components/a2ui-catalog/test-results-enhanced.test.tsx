/**
 * Enhanced TestResults Component Unit Tests
 * Comprehensive test coverage for all 4 status states, test suites, and logs
 */

import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TestResults, TestResultsProps } from '@/components/a2ui-catalog/test-results';
import { A2UIProps, A2UIEventType } from '@/lib/a2ui-types';

describe('Enhanced TestResults Component', () => {
  const mockOnEvent = jest.fn();
  const mockOnStatusChange = jest.fn();

  const createProps = (data: TestResultsProps): A2UIProps => ({
    type: 'a2ui.TestResults',
    data,
    metadata: { componentId: 'test-results-1' },
    onEvent: mockOnEvent,
  });

  beforeEach(() => {
    mockOnEvent.mockClear();
    mockOnStatusChange.mockClear();
  });

  describe('Status States', () => {
    test('renders with pending status', () => {
      const data: TestResultsProps = {
        testId: 'test-1',
        title: 'Unit Tests',
        status: 'pending',
        totalTests: 0,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('status-badge-pending')).toBeInTheDocument();
      expect(screen.getByText('Pending')).toBeInTheDocument();
      expect(screen.getByTestId('pending-state')).toBeInTheDocument();
    });

    test('renders with running status', () => {
      const data: TestResultsProps = {
        testId: 'test-2',
        title: 'Integration Tests',
        status: 'running',
        totalTests: 10,
        passedTests: 5,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('status-badge-running')).toBeInTheDocument();
      expect(screen.getByText('Running')).toBeInTheDocument();
      expect(screen.getByText('Progress')).toBeInTheDocument();
    });

    test('renders with passed status', () => {
      const data: TestResultsProps = {
        testId: 'test-3',
        title: 'E2E Tests',
        status: 'passed',
        totalTests: 50,
        passedTests: 50,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('status-badge-passed')).toBeInTheDocument();
      expect(screen.getByText('Passed')).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    test('renders with failed status', () => {
      const data: TestResultsProps = {
        testId: 'test-4',
        title: 'API Tests',
        status: 'failed',
        totalTests: 20,
        passedTests: 10,
        failedTests: 10,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('status-badge-failed')).toBeInTheDocument();
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });

    test('calls onStatusChange when status changes', () => {
      const data: TestResultsProps = {
        testId: 'test-5',
        title: 'Tests',
        status: 'running',
        totalTests: 10,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 0,
        onStatusChange: mockOnStatusChange,
      };

      render(<TestResults {...createProps(data)} />);

      expect(mockOnStatusChange).toHaveBeenCalledWith('running');
    });
  });

  describe('Title and TestId', () => {
    test('displays custom title', () => {
      const data: TestResultsProps = {
        testId: 'custom-test-1',
        title: 'My Custom Test Suite',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('test-title')).toHaveTextContent('My Custom Test Suite');
    });

    test('sets data-test-id attribute', () => {
      const data: TestResultsProps = {
        testId: 'unique-test-id',
        title: 'Tests',
        status: 'passed',
        totalTests: 5,
        passedTests: 5,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      const container = screen.getByTestId('test-results');
      expect(container).toHaveAttribute('data-test-id', 'unique-test-id');
      expect(container).toHaveAttribute('data-status', 'passed');
    });
  });

  describe('Test Suites', () => {
    test('renders test suites section when provided', () => {
      const data: TestResultsProps = {
        testId: 'test-6',
        title: 'Tests with Suites',
        status: 'passed',
        totalTests: 30,
        passedTests: 25,
        failedTests: 5,
        skippedTests: 0,
        testSuites: [
          {
            name: 'User Authentication',
            status: 'passed',
            tests: 10,
            passed: 10,
            failed: 0,
          },
          {
            name: 'Data Processing',
            status: 'failed',
            tests: 20,
            passed: 15,
            failed: 5,
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('test-suites')).toBeInTheDocument();
      expect(screen.getByText('Test Suites')).toBeInTheDocument();
      expect(screen.getByTestId('test-suite-0')).toBeInTheDocument();
      expect(screen.getByTestId('test-suite-1')).toBeInTheDocument();
    });

    test('displays suite names correctly', () => {
      const data: TestResultsProps = {
        testId: 'test-7',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        testSuites: [
          {
            name: 'Component Tests',
            status: 'passed',
            tests: 10,
            passed: 10,
            failed: 0,
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('suite-name-0')).toHaveTextContent('Component Tests');
    });

    test('displays suite status icons correctly', () => {
      const data: TestResultsProps = {
        testId: 'test-8',
        title: 'Tests',
        status: 'failed',
        totalTests: 30,
        passedTests: 20,
        failedTests: 5,
        skippedTests: 5,
        testSuites: [
          {
            name: 'Passed Suite',
            status: 'passed',
            tests: 10,
            passed: 10,
            failed: 0,
          },
          {
            name: 'Failed Suite',
            status: 'failed',
            tests: 10,
            passed: 5,
            failed: 5,
          },
          {
            name: 'Pending Suite',
            status: 'pending',
            tests: 10,
            passed: 0,
            failed: 0,
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('suite-status-passed-0')).toBeInTheDocument();
      expect(screen.getByTestId('suite-status-failed-1')).toBeInTheDocument();
      expect(screen.getByTestId('suite-status-pending-2')).toBeInTheDocument();
    });

    test('expands suite details when clicked', () => {
      const data: TestResultsProps = {
        testId: 'test-9',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        testSuites: [
          {
            name: 'Expandable Suite',
            status: 'passed',
            tests: 10,
            passed: 10,
            failed: 0,
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByTestId('suite-details-0')).not.toBeInTheDocument();

      const suite = screen.getByTestId('test-suite-0');
      fireEvent.click(suite);

      expect(screen.getByTestId('suite-details-0')).toBeInTheDocument();
    });

    test('emits event when suite is toggled', () => {
      const data: TestResultsProps = {
        testId: 'test-10',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        testSuites: [
          {
            name: 'Test Suite',
            status: 'passed',
            tests: 10,
            passed: 10,
            failed: 0,
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      const suite = screen.getByTestId('test-suite-0');
      fireEvent.click(suite);

      expect(mockOnEvent).toHaveBeenCalledWith(
        A2UIEventType.CLICK,
        expect.objectContaining({
          action: 'toggle_suite',
          suiteName: 'Test Suite',
          expanded: true,
        })
      );
    });

    test('displays suite pass rate correctly', () => {
      const data: TestResultsProps = {
        testId: 'test-11',
        title: 'Tests',
        status: 'passed',
        totalTests: 20,
        passedTests: 15,
        failedTests: 5,
        skippedTests: 0,
        testSuites: [
          {
            name: 'Suite with 75% pass rate',
            status: 'passed',
            tests: 20,
            passed: 15,
            failed: 5,
          },
        ],
      };

      render(<TestResults {...createProps(data)} />);

      // Check that 75% appears (both in summary and suite details)
      const percentages = screen.getAllByText(/75%/);
      expect(percentages.length).toBeGreaterThan(0);
      // Suite should show 15/20 passed and (75%) separately due to text node boundaries
      const suite = screen.getByTestId('test-suite-0');
      expect(within(suite).getByText(/15\/20 passed/)).toBeInTheDocument();
      expect(within(suite).getByText('75%')).toBeInTheDocument();
    });
  });

  describe('Logs Section', () => {
    test('renders logs section when logs are provided', () => {
      const data: TestResultsProps = {
        testId: 'test-12',
        title: 'Tests with Logs',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        logs: ['Test started', 'Running test suite', 'All tests passed'],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('logs-section')).toBeInTheDocument();
      expect(screen.getByText('Logs')).toBeInTheDocument();
    });

    test('logs are hidden by default', () => {
      const data: TestResultsProps = {
        testId: 'test-13',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        logs: ['Log entry 1', 'Log entry 2'],
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.queryByTestId('logs-content')).not.toBeInTheDocument();
    });

    test('shows logs when showDetails is true', () => {
      const data: TestResultsProps = {
        testId: 'test-14',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        logs: ['Log entry 1', 'Log entry 2'],
        showDetails: true,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('logs-content')).toBeInTheDocument();
    });

    test('toggles logs visibility when button is clicked', () => {
      const data: TestResultsProps = {
        testId: 'test-15',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        logs: ['Log entry'],
      };

      render(<TestResults {...createProps(data)} />);

      const toggleButton = screen.getByTestId('toggle-logs-button');
      expect(screen.queryByTestId('logs-content')).not.toBeInTheDocument();

      fireEvent.click(toggleButton);
      expect(screen.getByTestId('logs-content')).toBeInTheDocument();

      fireEvent.click(toggleButton);
      expect(screen.queryByTestId('logs-content')).not.toBeInTheDocument();
    });

    test('emits event when logs are toggled', () => {
      const data: TestResultsProps = {
        testId: 'test-16',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        logs: ['Log'],
      };

      render(<TestResults {...createProps(data)} />);

      const toggleButton = screen.getByTestId('toggle-logs-button');
      fireEvent.click(toggleButton);

      expect(mockOnEvent).toHaveBeenCalledWith(
        A2UIEventType.CLICK,
        expect.objectContaining({
          action: 'toggle_logs',
          visible: true,
        })
      );
    });

    test('displays all log entries', () => {
      const data: TestResultsProps = {
        testId: 'test-17',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        logs: ['Log 1', 'Log 2', 'Log 3', 'Log 4'],
        showDetails: true,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('log-0')).toHaveTextContent('Log 1');
      expect(screen.getByTestId('log-1')).toHaveTextContent('Log 2');
      expect(screen.getByTestId('log-2')).toHaveTextContent('Log 3');
      expect(screen.getByTestId('log-3')).toHaveTextContent('Log 4');
    });

    test('applies correct styling to error logs', () => {
      const data: TestResultsProps = {
        testId: 'test-18',
        title: 'Tests',
        status: 'failed',
        totalTests: 10,
        passedTests: 8,
        failedTests: 2,
        skippedTests: 0,
        logs: ['ERROR: Test failed', 'Test passed'],
        showDetails: true,
      };

      render(<TestResults {...createProps(data)} />);

      const errorLog = screen.getByTestId('log-0');
      expect(errorLog).toHaveClass('text-red-300');
      expect(errorLog).toHaveClass('bg-red-400/5');
    });

    test('applies correct styling to warning logs', () => {
      const data: TestResultsProps = {
        testId: 'test-19',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        logs: ['WARN: Deprecation notice'],
        showDetails: true,
      };

      render(<TestResults {...createProps(data)} />);

      const warnLog = screen.getByTestId('log-0');
      expect(warnLog).toHaveClass('text-orange-300');
    });

    test('applies correct styling to pass logs', () => {
      const data: TestResultsProps = {
        testId: 'test-20',
        title: 'Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        logs: ['Test PASSED successfully'],
        showDetails: true,
      };

      render(<TestResults {...createProps(data)} />);

      const passLog = screen.getByTestId('log-0');
      expect(passLog).toHaveClass('text-green-300');
    });
  });

  describe('Progress Bar', () => {
    test('shows gray color for pending status', () => {
      const data: TestResultsProps = {
        testId: 'test-21',
        title: 'Tests',
        status: 'pending',
        totalTests: 0,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveClass('bg-gray-400');
    });

    test('shows animated blue color for running status', () => {
      const data: TestResultsProps = {
        testId: 'test-22',
        title: 'Tests',
        status: 'running',
        totalTests: 10,
        passedTests: 5,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveClass('bg-blue-400');
      expect(progressBar).toHaveClass('animate-pulse');
    });

    test('changes label to "Progress" for running status', () => {
      const data: TestResultsProps = {
        testId: 'test-23',
        title: 'Tests',
        status: 'running',
        totalTests: 10,
        passedTests: 3,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('Progress')).toBeInTheDocument();
      expect(screen.queryByText('Pass Rate')).not.toBeInTheDocument();
    });
  });

  describe('Empty States', () => {
    test('shows running empty state', () => {
      const data: TestResultsProps = {
        testId: 'test-24',
        title: 'Tests',
        status: 'running',
        totalTests: 0,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('running-state')).toBeInTheDocument();
      expect(screen.getByText('Tests are currently running...')).toBeInTheDocument();
    });

    test('shows pending empty state', () => {
      const data: TestResultsProps = {
        testId: 'test-25',
        title: 'Tests',
        status: 'pending',
        totalTests: 0,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('pending-state')).toBeInTheDocument();
      expect(screen.getByText('Tests are pending execution...')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    test('handles zero tests correctly', () => {
      const data: TestResultsProps = {
        testId: 'test-26',
        title: 'Empty Tests',
        status: 'passed',
        totalTests: 0,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('total-tests')).toHaveTextContent('0');
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    test('handles all tests passed', () => {
      const data: TestResultsProps = {
        testId: 'test-27',
        title: 'Perfect Score',
        status: 'passed',
        totalTests: 100,
        passedTests: 100,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('100%')).toBeInTheDocument();
      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveClass('bg-green-400');
    });

    test('handles all tests failed', () => {
      const data: TestResultsProps = {
        testId: 'test-28',
        title: 'All Failed',
        status: 'failed',
        totalTests: 50,
        passedTests: 0,
        failedTests: 50,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByText('0%')).toBeInTheDocument();
      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveClass('bg-red-400');
    });

    test('handles missing optional fields', () => {
      const data: TestResultsProps = {
        testId: 'test-29',
        title: 'Minimal Data',
        status: 'passed',
        totalTests: 10,
        passedTests: 8,
        failedTests: 2,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('test-results')).toBeInTheDocument();
      expect(screen.queryByTestId('test-suites')).not.toBeInTheDocument();
      expect(screen.queryByTestId('logs-section')).not.toBeInTheDocument();
      expect(screen.queryByTestId('duration')).not.toBeInTheDocument();
    });

    test('handles duration display', () => {
      const data: TestResultsProps = {
        testId: 'test-30',
        title: 'Timed Tests',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
        duration: 12.45,
      };

      render(<TestResults {...createProps(data)} />);

      expect(screen.getByTestId('duration')).toBeInTheDocument();
      expect(screen.getByText('12.45s')).toBeInTheDocument();
    });
  });

  describe('Responsive and Dark Theme', () => {
    test('applies dark theme classes', () => {
      const data: TestResultsProps = {
        testId: 'test-31',
        title: 'Dark Theme Test',
        status: 'passed',
        totalTests: 10,
        passedTests: 10,
        failedTests: 0,
        skippedTests: 0,
      };

      render(<TestResults {...createProps(data)} />);

      const container = screen.getByTestId('test-results');
      expect(container).toHaveClass('bg-gray-900');
      expect(container).toHaveClass('border-gray-800');
      expect(container).toHaveClass('text-gray-100');
    });
  });
});
