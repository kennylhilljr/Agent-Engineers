/**
 * FileTreeSkeleton Component
 * Loading skeleton for FileTree component
 */

'use client';

import React from 'react';

export interface FileTreeSkeletonProps {
  depth?: number;
  className?: string;
}

export const FileTreeSkeleton: React.FC<FileTreeSkeletonProps> = ({
  depth = 3,
  className = '',
}) => {
  return (
    <div
      className={`space-y-2 ${className}`}
      data-testid="file-tree-skeleton"
    >
      {/* Root items */}
      {Array.from({ length: depth }).map((_, i) => (
        <div key={i} className="space-y-2">
          {/* Parent item */}
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-gray-700 rounded animate-pulse" />
            <div className="h-4 bg-gray-700 rounded w-32 animate-pulse" />
          </div>

          {/* Nested children (if not last) */}
          {i < depth - 1 && (
            <div className="ml-6 space-y-2">
              {Array.from({ length: 2 }).map((_, j) => (
                <div key={j} className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-gray-700 rounded animate-pulse" />
                  <div
                    className="h-4 bg-gray-700 rounded animate-pulse"
                    style={{ width: `${Math.random() * 60 + 40}%` }}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

FileTreeSkeleton.displayName = 'FileTreeSkeleton';

export default FileTreeSkeleton;
