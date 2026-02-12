/**
 * TestResults Component
 * Displays test execution results with coverage metrics
 * Part of A2UI Component Catalog
 */

'use client';

import React from 'react';
import { TestResultsProps, TestResult } from '../types';
import { CheckCircle, XCircle, SkipForward, Loader2 } from 'lucide-react';

const statusConfig: Record<TestResult['status'], {
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  label: string;
}> = {
  passed: { icon: CheckCircle, color: 'text-green-400', label: 'Passed' },
  failed: { icon: XCircle, color: 'text-red-400', label: 'Failed' },
  skipped: { icon: SkipForward, color: 'text-gray-400', label: 'Skipped' },
  running: { icon: Loader2, color: 'text-blue-400', label: 'Running' },
};

export const TestResults: React.FC<TestResultsProps> = ({
  tests,
  coverage,
  status,
  totalTests,
  passedTests,
  failedTests,
  skippedTests,
  className = '',
}) => {
  const total = totalTests ?? tests.length;
  const passed = passedTests ?? tests.filter(t => t.status === 'passed').length;
  const failed = failedTests ?? tests.filter(t => t.status === 'failed').length;
  const skipped = skippedTests ?? tests.filter(t => t.status === 'skipped').length;
  const isRunning = status === 'running';
  const hasFailed = failed > 0;

  const statusBorder = hasFailed
    ? 'border-red-600'
    : status === 'completed'
    ? 'border-green-600'
    : 'border-gray-600';

  const statusBg = hasFailed
    ? 'bg-red-900/30'
    : status === 'completed'
    ? 'bg-green-900/30'
    : 'bg-gray-800';

  return (
    <div
      className={`rounded-lg border-2 ${statusBorder} ${statusBg} overflow-hidden ${className}`}
      role="region"
      aria-label="Test Results"
      data-testid="test-results"
      data-status={status}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isRunning && (
              <Loader2 className="w-5 h-5 text-blue-400 animate-spin" aria-hidden="true" />
            )}
            <h3 className="text-lg font-semibold text-white">
              Test Results
            </h3>
          </div>
          <div className={`px-3 py-1 rounded-full text-xs font-semibold ${
            isRunning ? 'text-blue-400 border-blue-600' :
            hasFailed ? 'text-red-400 border-red-600' :
            status === 'completed' ? 'text-green-400 border-green-600' :
            'text-gray-400 border-gray-600'
          } bg-gray-800 border`}>
            {isRunning ? 'Running...' : hasFailed ? 'Failed' : status === 'completed' ? 'Passed' : 'Idle'}
          </div>
        </div>

        {/* Summary counts */}
        <div className="flex items-center gap-4 mt-3 text-sm">
          <span className="text-gray-400">
            Total: <span className="text-white font-semibold">{total}</span>
          </span>
          <span className="text-green-400">
            Passed: <span className="font-semibold">{passed}</span>
          </span>
          {failed > 0 && (
            <span className="text-red-400">
              Failed: <span className="font-semibold">{failed}</span>
            </span>
          )}
          {skipped > 0 && (
            <span className="text-gray-400">
              Skipped: <span className="font-semibold">{skipped}</span>
            </span>
          )}
        </div>
      </div>

      {/* Test list */}
      <div className="divide-y divide-gray-700/50 max-h-80 overflow-y-auto">
        {tests.map((test, index) => {
          const config = statusConfig[test.status];
          const Icon = config.icon;
          return (
            <div
              key={test.name + index}
              className="px-4 py-2.5 flex items-start gap-3 hover:bg-gray-800/50 transition-colors"
              data-testid={`test-item-${test.status}`}
            >
              <Icon
                className={`w-4 h-4 mt-0.5 flex-shrink-0 ${config.color} ${
                  test.status === 'running' ? 'animate-spin' : ''
                }`}
                aria-label={config.label}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm text-white truncate">{test.name}</span>
                  {test.duration !== undefined && (
                    <span className="text-xs text-gray-500 flex-shrink-0">
                      {test.duration}ms
                    </span>
                  )}
                </div>
                {test.file && (
                  <span className="text-xs text-gray-500 block truncate">{test.file}</span>
                )}
                {test.errorMessage && (
                  <p className="text-xs text-red-300 mt-1 font-mono bg-red-900/20 px-2 py-1 rounded">
                    {test.errorMessage}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Coverage */}
      {coverage && (
        <div className="p-4 border-t border-gray-700 bg-gray-800/50">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Coverage
          </h4>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Lines', value: coverage.lines },
              { label: 'Branches', value: coverage.branches },
              { label: 'Functions', value: coverage.functions },
              { label: 'Statements', value: coverage.statements },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center justify-between text-sm">
                <span className="text-gray-400">{label}</span>
                <span className={`font-semibold ${
                  value >= 80 ? 'text-green-400' : value >= 50 ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {value}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

TestResults.displayName = 'TestResults';

export default TestResults;
