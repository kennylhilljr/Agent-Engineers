'use client';

import React, { useState, useMemo } from 'react';

/**
 * ActivityItem Component
 * Displays individual activity entries with timeline visualization
 *
 * Features:
 * - 8 event types with color-coded dots
 * - 4 status states (pending, in_progress, completed, failed)
 * - Relative timestamp formatting
 * - Expandable metadata section
 * - Timeline connecting lines
 * - Full accessibility support
 */

/**
 * Activity event types
 */
export type ActivityEventType =
  | 'task_started'
  | 'task_completed'
  | 'file_modified'
  | 'command_executed'
  | 'test_run'
  | 'decision_made'
  | 'error_occurred'
  | 'milestone_reached';

/**
 * Activity status states
 */
export type ActivityStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

export interface ActivityItemProps {
  id: string;
  type: ActivityEventType;
  title: string;
  description?: string;
  timestamp: Date;
  status?: ActivityStatus;
  author?: string;
  metadata?: Record<string, unknown>;
  expanded?: boolean;
  onExpand?: (expanded: boolean) => void;
  className?: string;
}

// Event type to display name mapping
const EVENT_TYPE_LABELS: Record<ActivityEventType, string> = {
  task_started: 'Task Started',
  task_completed: 'Task Completed',
  file_modified: 'File Modified',
  command_executed: 'Command Executed',
  test_run: 'Test Run',
  decision_made: 'Decision Made',
  error_occurred: 'Error Occurred',
  milestone_reached: 'Milestone Reached',
};

// Event type to color mapping
const EVENT_TYPE_COLORS: Record<ActivityEventType, string> = {
  task_started: 'bg-blue-500',
  task_completed: 'bg-green-500',
  file_modified: 'bg-purple-500',
  command_executed: 'bg-orange-500',
  test_run: 'bg-indigo-500',
  decision_made: 'bg-yellow-500',
  error_occurred: 'bg-red-500',
  milestone_reached: 'bg-emerald-500',
};

// Status to display name and color mapping
const STATUS_CONFIG: Record<ActivityStatus, { label: string; color: string }> = {
  pending: { label: 'Pending', color: 'text-gray-400' },
  in_progress: { label: 'In Progress', color: 'text-blue-400' },
  completed: { label: 'Completed', color: 'text-green-400' },
  failed: { label: 'Failed', color: 'text-red-400' },
};

// Event type to icon mapping
const EVENT_TYPE_ICONS: Record<ActivityEventType, string> = {
  task_started: '▶',
  task_completed: '✓',
  file_modified: '📝',
  command_executed: '⚙',
  test_run: '🧪',
  decision_made: '🎯',
  error_occurred: '⚠',
  milestone_reached: '🏁',
};

/**
 * Format relative time
 */
function formatRelativeTime(timestamp: Date): string {
  const now = new Date();
  const diff = now.getTime() - timestamp.getTime();
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const weeks = Math.floor(days / 7);
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);

  if (seconds < 30) return 'just now';
  if (minutes === 0) return 'just now';
  if (minutes === 1) return '1 minute ago';
  if (minutes < 60) return `${minutes} minutes ago`;
  if (hours === 1) return '1 hour ago';
  if (hours < 24) return `${hours} hours ago`;
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days} days ago`;
  if (weeks === 1) return '1 week ago';
  if (weeks < 4) return `${weeks} weeks ago`;
  if (months === 1) return '1 month ago';
  if (months < 12) return `${months} months ago`;
  if (years === 1) return '1 year ago';
  return `${years} years ago`;
}

/**
 * Format date for title attribute
 */
function formatFullDate(timestamp: Date): string {
  return timestamp.toLocaleString();
}

export function ActivityItem({
  id,
  type,
  title,
  description,
  timestamp,
  status,
  author,
  metadata,
  expanded: initialExpanded = false,
  onExpand,
  className = '',
}: ActivityItemProps) {
  const [isExpanded, setIsExpanded] = useState(initialExpanded);

  // Check if metadata exists and is not empty
  const hasMetadata = useMemo(() => {
    return metadata && Object.keys(metadata).length > 0;
  }, [metadata]);

  const handleExpand = () => {
    const newExpanded = !isExpanded;
    setIsExpanded(newExpanded);
    onExpand?.(newExpanded);
  };

  const dotColor = EVENT_TYPE_COLORS[type];
  const eventLabel = EVENT_TYPE_LABELS[type];
  const icon = EVENT_TYPE_ICONS[type];
  const relativeTime = formatRelativeTime(timestamp);
  const fullDate = formatFullDate(timestamp);

  return (
    <div
      data-testid="activity-item"
      data-event-type={type}
      {...(status && { 'data-status': status })}
      className={`relative flex gap-4 py-4 px-4 rounded-lg border border-gray-800 bg-gray-900/50 hover:bg-gray-900 transition-colors ${className}`}
    >
      {/* Timeline Column */}
      <div className="relative flex flex-col items-center pt-1">
        {/* Timeline Dot */}
        <div
          data-testid="activity-dot"
          className={`w-4 h-4 rounded-full ${dotColor} flex items-center justify-center flex-shrink-0 ring-4 ring-gray-900`}
          aria-hidden="true"
        >
          {/* Icon in dot */}
          <span
            data-testid="activity-icon"
            className="text-xs text-white font-bold"
            aria-hidden="true"
          >
            {icon}
          </span>
        </div>

        {/* Timeline Connecting Line */}
        <div
          data-testid="timeline-line"
          className="w-0.5 h-12 bg-gray-700 mt-1"
          aria-hidden="true"
        />
      </div>

      {/* Content Column */}
      <div className="flex-1 min-w-0">
        {/* Header Section */}
        <div className="flex flex-col gap-2">
          {/* Title and Badge Row */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <h3
                data-testid="activity-title"
                className="text-sm font-semibold text-gray-100 break-words"
              >
                {title}
              </h3>
            </div>

            {/* Event Type Badge */}
            <span
              data-testid="event-type-badge"
              className="inline-block px-2 py-1 text-xs font-medium bg-gray-800 text-gray-300 rounded whitespace-nowrap flex-shrink-0"
            >
              {eventLabel}
            </span>
          </div>

          {/* Metadata Row: Status, Timestamp, Author */}
          <div className="flex items-center gap-3 flex-wrap text-xs text-gray-400">
            {/* Status Badge */}
            {status && (
              <span
                data-testid="status-badge"
                className={`font-medium ${STATUS_CONFIG[status].color}`}
              >
                {STATUS_CONFIG[status].label}
              </span>
            )}

            {/* Timestamp */}
            <time
              data-testid="activity-timestamp"
              dateTime={timestamp.toISOString()}
              title={fullDate}
              className="text-gray-500"
            >
              {relativeTime}
            </time>

            {/* Author */}
            {author && (
              <span data-testid="activity-author" className="text-gray-500">
                by {author}
              </span>
            )}
          </div>
        </div>

        {/* Description */}
        {description && (
          <p
            data-testid="activity-description"
            className="mt-2 text-sm text-gray-400 break-words"
          >
            {description}
          </p>
        )}

        {/* Expand Button and Metadata Section */}
        {hasMetadata && (
          <div className="mt-3">
            <button
              data-testid="expand-button"
              onClick={handleExpand}
              aria-expanded={isExpanded}
              className="text-xs font-medium text-blue-400 hover:text-blue-300 transition-colors"
            >
              {isExpanded ? 'Hide details' : 'Show details'}
            </button>

            {/* Metadata Section */}
            {isExpanded && (
              <div
                data-testid="metadata-section"
                className="mt-3 p-3 bg-gray-950/50 rounded border border-gray-800 text-xs text-gray-400 space-y-2"
              >
                {Object.entries(metadata || {}).map(([key, value]) => (
                  <div key={key} className="flex gap-2">
                    <span className="font-medium text-gray-500">{key}:</span>
                    <span className="text-gray-400 break-words">
                      {typeof value === 'object'
                        ? JSON.stringify(value)
                        : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ActivityItem;
