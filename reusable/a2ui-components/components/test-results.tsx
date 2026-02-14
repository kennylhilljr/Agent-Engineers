import React, { useState } from 'react';
import { A2UIProps, TestResultsData, TestCase, TestSuite, A2UIEventType } from '@/lib/a2ui-types';
import { cn } from '@/lib/utils';
import { CheckCircle2, XCircle, Circle, ChevronDown, ChevronRight, Clock } from 'lucide-react';

/**
 * TestResults - Displays test execution results with pass/fail status and test case details
 * Fully implemented A2UI component with dark theme
 * Features: Summary statistics, progress bar, test suites with expand/collapse, individual test cases, error details
 */
export function TestResults({ type, data, metadata, onEvent }: A2UIProps) {
  const testData = data as TestResultsData;
  const [expandedTests, setExpandedTests] = useState<Set<number>>(new Set());
  const [expandedSuites, setExpandedSuites] = useState<Set<string>>(new Set());

  const totalTests = testData.totalTests || 0;
  const passedTests = testData.passedTests || 0;
  const failedTests = testData.failedTests || 0;
  const skippedTests = testData.skippedTests || 0;
  const duration = testData.duration;
  const testCases = testData.testCases || [];
  const testSuites = testData.testSuites || [];

  // Calculate percentages
  const passRate = totalTests > 0 ? Math.round((passedTests / totalTests) * 100) : 0;
  const failRate = totalTests > 0 ? Math.round((failedTests / totalTests) * 100) : 0;

  // Determine progress bar color based on pass rate
  const getProgressColor = () => {
    if (passRate >= 80) return 'bg-green-400';
    if (passRate >= 50) return 'bg-orange-400';
    return 'bg-red-400';
  };

  // Format duration
  const formatDuration = (seconds?: number) => {
    if (seconds === undefined) return '';
    if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
    return `${seconds.toFixed(2)}s`;
  };

  // Toggle error details expansion
  const toggleExpand = (index: number) => {
    const newExpanded = new Set(expandedTests);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedTests(newExpanded);

    // Emit event
    if (onEvent) {
      onEvent(A2UIEventType.CLICK, {
        action: 'toggle_test_details',
        testIndex: index,
        expanded: !expandedTests.has(index)
      });
    }
  };

  // Toggle suite expansion
  const toggleSuite = (suiteName: string) => {
    const newExpanded = new Set(expandedSuites);
    if (newExpanded.has(suiteName)) {
      newExpanded.delete(suiteName);
    } else {
      newExpanded.add(suiteName);
    }
    setExpandedSuites(newExpanded);

    // Emit event
    if (onEvent) {
      onEvent(A2UIEventType.CLICK, {
        action: 'toggle_suite',
        suiteName,
        expanded: !expandedSuites.has(suiteName)
      });
    }
  };

  // Render status icon
  const renderStatusIcon = (status: TestCase['status']) => {
    switch (status) {
      case 'passed':
        return <CheckCircle2 className="w-4 h-4 text-green-400" data-testid="icon-passed" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-400" data-testid="icon-failed" />;
      case 'skipped':
        return <Circle className="w-4 h-4 text-gray-400" data-testid="icon-skipped" />;
      case 'running':
        return <Clock className="w-4 h-4 text-blue-400 animate-pulse" data-testid="icon-running" />;
      default:
        return <Circle className="w-4 h-4 text-gray-400" />;
    }
  };

  // Render status badge
  const renderStatusBadge = (status: TestCase['status']) => {
    const statusConfig = {
      passed: { label: 'Passed', color: 'text-green-400 bg-green-400/10 border-green-400/20' },
      failed: { label: 'Failed', color: 'text-red-400 bg-red-400/10 border-red-400/20' },
      skipped: { label: 'Skipped', color: 'text-gray-400 bg-gray-400/10 border-gray-400/20' },
      running: { label: 'Running', color: 'text-blue-400 bg-blue-400/10 border-blue-400/20' }
    };

    const config = statusConfig[status];
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-md border",
          config.color
        )}
        data-testid={`badge-${status}`}
      >
        {renderStatusIcon(status)}
        {config.label}
      </span>
    );
  };

  // Truncate long error messages
  const truncateError = (error: string, maxLength: number = 100) => {
    if (error.length <= maxLength) return error;
    return error.substring(0, maxLength) + '...';
  };

  return (
    <div
      className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-gray-100"
      data-testid="test-results"
    >
      {/* Summary Section */}
      <div className="space-y-4 mb-6">
        <h3 className="text-xl font-semibold text-gray-100">Test Results</h3>

        {/* Test Counts */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4" data-testid="test-summary">
          <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
            <div className="text-2xl font-bold text-gray-100">{totalTests}</div>
            <div className="text-xs text-gray-400 mt-1">Total Tests</div>
          </div>
          <div className="bg-green-400/10 rounded-lg p-3 border border-green-400/20">
            <div className="text-2xl font-bold text-green-400">{passedTests}</div>
            <div className="text-xs text-gray-400 mt-1">Passed ({passRate}%)</div>
          </div>
          <div className="bg-red-400/10 rounded-lg p-3 border border-red-400/20">
            <div className="text-2xl font-bold text-red-400">{failedTests}</div>
            <div className="text-xs text-gray-400 mt-1">Failed ({failRate}%)</div>
          </div>
          {skippedTests > 0 && (
            <div className="bg-gray-400/10 rounded-lg p-3 border border-gray-400/20">
              <div className="text-2xl font-bold text-gray-400">{skippedTests}</div>
              <div className="text-xs text-gray-400 mt-1">Skipped</div>
            </div>
          )}
        </div>

        {/* Progress Bar */}
        <div className="space-y-2" data-testid="progress-bar-container">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Pass Rate</span>
            <span className={cn(
              "font-semibold",
              passRate >= 80 ? "text-green-400" : passRate >= 50 ? "text-orange-400" : "text-red-400"
            )}>
              {passRate}%
            </span>
          </div>
          <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full transition-all duration-500 ease-out",
                getProgressColor()
              )}
              style={{ width: `${passRate}%` }}
              data-testid="progress-bar"
            />
          </div>
        </div>

        {/* Duration */}
        {duration !== undefined && (
          <div className="text-sm text-gray-400" data-testid="duration">
            Total Duration: <span className="font-medium text-gray-300">{formatDuration(duration)}</span>
          </div>
        )}
      </div>

      {/* Test Suites */}
      {testSuites.length > 0 && (
        <div className="space-y-4 mb-6" data-testid="test-suites">
          <h4 className="text-lg font-semibold text-gray-100 mb-4">Test Suites</h4>
          {testSuites.map((suite, suiteIndex) => {
            const isSuiteExpanded = expandedSuites.has(suite.name);
            const suitePassRate = (suite.total || 0) > 0 ? Math.round((suite.passed / (suite.total || 1)) * 100) : 0;

            return (
              <div
                key={suiteIndex}
                className="bg-gray-800/30 border border-gray-700 rounded-lg overflow-hidden"
                data-testid={`test-suite-${suiteIndex}`}
              >
                {/* Suite Header */}
                <button
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800/50 transition-colors"
                  onClick={() => toggleSuite(suite.name)}
                  data-testid={`suite-toggle-${suiteIndex}`}
                >
                  <div className="flex items-center gap-3">
                    {isSuiteExpanded ? (
                      <ChevronDown className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-gray-400" />
                    )}
                    <div className="text-left">
                      <div className="font-semibold text-gray-100" data-testid={`suite-name-${suiteIndex}`}>
                        {suite.name}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        {suite.total} tests • {suite.passed} passed • {suite.failed} failed
                        {(suite.skipped || 0) > 0 && ` • ${suite.skipped} skipped`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-sm text-gray-400">
                      {formatDuration(suite.duration)}
                    </div>
                    <div className={cn(
                      "text-sm font-semibold",
                      suitePassRate >= 80 ? "text-green-400" : suitePassRate >= 50 ? "text-orange-400" : "text-red-400"
                    )}>
                      {suitePassRate}%
                    </div>
                  </div>
                </button>

                {/* Suite Tests */}
                {isSuiteExpanded && Array.isArray(suite.tests) && (
                  <div className="border-t border-gray-700 p-4 space-y-2" data-testid={`suite-tests-${suiteIndex}`}>
                    {suite.tests.map((test, testIndex) => {
                      const testKey = `${suiteIndex}-${testIndex}`;
                      const isExpanded = expandedTests.has(testIndex);
                      const hasError = test.status === 'failed' && test.error;

                      return (
                        <div
                          key={testKey}
                          className={cn(
                            "bg-gray-900/50 border rounded-lg transition-all duration-200 p-3",
                            test.status === 'passed' && "border-gray-700 hover:border-green-400/30",
                            test.status === 'failed' && "border-red-400/30 hover:border-red-400/50",
                            test.status === 'skipped' && "border-gray-700 hover:border-gray-600",
                            hasError && "cursor-pointer"
                          )}
                          data-testid={`suite-test-${testKey}`}
                          onClick={() => hasError && toggleExpand(testIndex)}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                {renderStatusBadge(test.status)}
                                {test.duration !== undefined && (
                                  <span className="text-xs text-gray-500">
                                    {formatDuration(test.duration)}
                                  </span>
                                )}
                              </div>
                              <div className="text-sm text-gray-200">
                                {test.name}
                              </div>
                              {hasError && !isExpanded && (
                                <div className="text-xs text-red-400 mt-2 font-mono">
                                  {truncateError(test.error!)}
                                </div>
                              )}
                            </div>
                            {hasError && (
                              <button className="flex-shrink-0 text-gray-400 hover:text-gray-200">
                                {isExpanded ? (
                                  <ChevronDown className="w-4 h-4" />
                                ) : (
                                  <ChevronRight className="w-4 h-4" />
                                )}
                              </button>
                            )}
                          </div>
                          {hasError && isExpanded && (
                            <div className="mt-2 pt-2 border-t border-gray-700">
                              <div className="text-xs text-gray-400 mb-1 font-semibold">Error Details:</div>
                              <div className="bg-gray-900 rounded p-2 text-xs text-red-300 font-mono whitespace-pre-wrap break-words">
                                {test.error}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Test Case List */}
      {testCases.length > 0 && (
        <div className="space-y-3" data-testid="test-case-list">
          <h4 className="text-lg font-semibold text-gray-100 mb-4">Test Cases</h4>
          {testCases.map((testCase, index) => {
            const isExpanded = expandedTests.has(index);
            const hasError = testCase.status === 'failed' && testCase.error;

            return (
              <div
                key={index}
                className={cn(
                  "bg-gray-800/50 border rounded-lg transition-all duration-200",
                  testCase.status === 'passed' && "border-gray-700 hover:border-green-400/30",
                  testCase.status === 'failed' && "border-red-400/30 hover:border-red-400/50",
                  testCase.status === 'skipped' && "border-gray-700 hover:border-gray-600",
                  hasError && "cursor-pointer"
                )}
                data-testid={`test-case-${index}`}
                onClick={() => hasError && toggleExpand(index)}
              >
                <div className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        {renderStatusBadge(testCase.status)}
                        {testCase.duration !== undefined && (
                          <span className="text-xs text-gray-500" data-testid={`test-duration-${index}`}>
                            {formatDuration(testCase.duration)}
                          </span>
                        )}
                      </div>
                      <div className="text-sm font-medium text-gray-200 break-words" data-testid={`test-name-${index}`}>
                        {testCase.name}
                      </div>
                      {hasError && !isExpanded && (
                        <div className="text-xs text-red-400 mt-2 font-mono" data-testid={`error-preview-${index}`}>
                          {truncateError(testCase.error!)}
                        </div>
                      )}
                    </div>
                    {hasError && (
                      <button
                        className="flex-shrink-0 text-gray-400 hover:text-gray-200 transition-colors"
                        data-testid={`expand-button-${index}`}
                        aria-label={isExpanded ? "Collapse error details" : "Expand error details"}
                      >
                        {isExpanded ? (
                          <ChevronDown className="w-5 h-5" />
                        ) : (
                          <ChevronRight className="w-5 h-5" />
                        )}
                      </button>
                    )}
                  </div>

                  {/* Expanded Error Details */}
                  {hasError && isExpanded && (
                    <div
                      className="mt-3 pt-3 border-t border-gray-700 animate-in slide-in-from-top-2 duration-200"
                      data-testid={`error-details-${index}`}
                    >
                      <div className="text-xs text-gray-400 mb-1 font-semibold">Error Details:</div>
                      <div className="bg-gray-900 rounded p-3 text-xs text-red-300 font-mono whitespace-pre-wrap break-words">
                        {testCase.error}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
