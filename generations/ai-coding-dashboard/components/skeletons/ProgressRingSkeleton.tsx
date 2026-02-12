/**
 * ProgressRingSkeleton Component
 * Loading skeleton for ProgressRing component
 */

'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { rotate } from '@/lib/animations';

export interface ProgressRingSkeletonProps {
  size?: 'small' | 'medium' | 'large';
  showMetrics?: boolean;
  className?: string;
}

const sizeConfig = {
  small: {
    container: 'w-24 h-24',
    strokeWidth: 4,
  },
  medium: {
    container: 'w-32 h-32',
    strokeWidth: 6,
  },
  large: {
    container: 'w-48 h-48',
    strokeWidth: 8,
  },
};

export const ProgressRingSkeleton: React.FC<ProgressRingSkeletonProps> = ({
  size = 'medium',
  showMetrics = true,
  className = '',
}) => {
  const config = sizeConfig[size];

  return (
    <div
      className={`flex flex-col items-center gap-4 ${className}`}
      data-testid="progress-ring-skeleton"
    >
      {/* Ring skeleton with rotation animation */}
      <div className={`relative ${config.container}`}>
        <motion.svg
          className="transform -rotate-90"
          width="100%"
          height="100%"
          viewBox="0 0 100 100"
          variants={rotate}
          animate="animate"
        >
          {/* Background circle */}
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="currentColor"
            strokeWidth={config.strokeWidth}
            className="text-gray-700"
          />
          {/* Animated arc */}
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="currentColor"
            strokeWidth={config.strokeWidth}
            strokeDasharray="70 212"
            className="text-gray-600 opacity-60"
          />
        </motion.svg>

        {/* Center content placeholder */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="h-8 w-16 bg-gray-700 rounded animate-pulse mb-1" />
          <div className="h-3 w-12 bg-gray-700 rounded animate-pulse" />
        </div>
      </div>

      {/* Metrics skeleton */}
      {showMetrics && (
        <div className="flex items-center gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex flex-col items-center gap-1">
              <div className="flex items-center gap-1.5">
                <div className="w-4 h-4 bg-gray-700 rounded-full animate-pulse" />
                <div className="h-4 w-8 bg-gray-700 rounded animate-pulse" />
              </div>
              <div className="h-3 w-12 bg-gray-700 rounded animate-pulse" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

ProgressRingSkeleton.displayName = 'ProgressRingSkeleton';

export default ProgressRingSkeleton;
