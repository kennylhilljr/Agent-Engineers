/**
 * TaskCardSkeleton Component
 * Loading skeleton for TaskCard with shimmer animation
 */

'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { shimmer } from '@/lib/animations';

export interface TaskCardSkeletonProps {
  className?: string;
}

export const TaskCardSkeleton: React.FC<TaskCardSkeletonProps> = ({ className = '' }) => {
  return (
    <div
      className={`relative rounded-lg border-2 border-gray-700 bg-gray-800/50 overflow-hidden ${className}`}
      data-testid="task-card-skeleton"
    >
      {/* Shimmer overlay */}
      <motion.div
        className="absolute inset-0 bg-gradient-to-r from-transparent via-gray-700/30 to-transparent"
        variants={shimmer}
        initial="initial"
        animate="animate"
        style={{
          backgroundSize: '200% 100%',
        }}
      />

      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 flex-1">
            {/* Icon placeholder */}
            <div className="w-5 h-5 mt-0.5 bg-gray-700 rounded-full animate-pulse" />
            <div className="flex-1 space-y-2">
              {/* Title placeholder */}
              <div className="h-5 bg-gray-700 rounded w-3/4 animate-pulse" />
              {/* Category badge placeholder */}
              <div className="h-4 bg-gray-700 rounded w-20 animate-pulse" />
            </div>
          </div>
          {/* Status badge placeholder */}
          <div className="h-6 bg-gray-700 rounded-full w-24 animate-pulse" />
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Description placeholders */}
        <div className="space-y-2">
          <div className="h-4 bg-gray-700 rounded w-full animate-pulse" />
          <div className="h-4 bg-gray-700 rounded w-5/6 animate-pulse" />
        </div>

        {/* Progress bar placeholder */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <div className="h-3 bg-gray-700 rounded w-16 animate-pulse" />
            <div className="h-3 bg-gray-700 rounded w-12 animate-pulse" />
          </div>
          <div className="h-2 bg-gray-700 rounded-full w-full animate-pulse" />
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 bg-gray-800/50 border-t border-gray-700">
        <div className="flex items-center justify-between">
          <div className="h-3 bg-gray-700 rounded w-32 animate-pulse" />
        </div>
      </div>
    </div>
  );
};

TaskCardSkeleton.displayName = 'TaskCardSkeleton';

export default TaskCardSkeleton;
