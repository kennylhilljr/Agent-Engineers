/**
 * TestResultsSkeleton Component
 * Loading skeleton for test results display
 */

'use client';

import React from 'react';

export interface TestResultsSkeletonProps {
  testCount?: number;
  className?: string;
}

export const TestResultsSkeleton: React.FC<TestResultsSkeletonProps> = ({
  testCount = 5,
  className = '',
}) => {
  return (
    <div
      className={`space-y-3 ${className}`}
      data-testid="test-results-skeleton"
    >
      {/* Summary header */}
      <div className="flex items-center justify-between p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 bg-gray-700 rounded-full animate-pulse" />
          <div className="h-5 bg-gray-700 rounded w-48 animate-pulse" />
        </div>
        <div className="h-5 bg-gray-700 rounded w-24 animate-pulse" />
      </div>

      {/* Individual test items */}
      <div className="space-y-2">
        {Array.from({ length: testCount }).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-3 p-3 bg-gray-800/30 border border-gray-700 rounded-md"
          >
            {/* Status icon */}
            <div className="w-5 h-5 bg-gray-700 rounded-full animate-pulse flex-shrink-0" />

            {/* Test name */}
            <div
              className="h-4 bg-gray-700 rounded animate-pulse"
              style={{ width: `${Math.random() * 40 + 30}%` }}
            />

            {/* Spacer */}
            <div className="flex-1" />

            {/* Duration */}
            <div className="h-4 bg-gray-700 rounded w-16 animate-pulse" />
          </div>
        ))}
      </div>

      {/* Stats footer */}
      <div className="flex items-center gap-4 p-3 bg-gray-800/30 border border-gray-700 rounded-md">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="w-3 h-3 bg-gray-700 rounded-full animate-pulse" />
            <div className="h-4 bg-gray-700 rounded w-20 animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
};

TestResultsSkeleton.displayName = 'TestResultsSkeleton';

export default TestResultsSkeleton;
