import React from 'react';
import { A2UIProps, ProgressRingData } from '@/lib/a2ui-types';
import { cn } from '@/lib/utils';
import { CheckCircle2, FileText, FlaskConical } from 'lucide-react';

/**
 * ProgressRing - Circular progress indicator component
 * Displays overall completion percentage with metrics
 * Fully implemented A2UI component with dark theme
 */
export function ProgressRing({ type, data, metadata, onEvent }: A2UIProps) {
  const progressData = data as ProgressRingData;
  const percentage = Math.min(100, Math.max(0, progressData.percentage || 0));

  // Color-code ring based on completion
  const getColorClasses = (pct: number) => {
    if (pct < 50) {
      return {
        stroke: 'stroke-red-500',
        text: 'text-red-400',
        glow: 'shadow-red-500/20',
      };
    } else if (pct < 80) {
      return {
        stroke: 'stroke-orange-500',
        text: 'text-orange-400',
        glow: 'shadow-orange-500/20',
      };
    } else {
      return {
        stroke: 'stroke-green-500',
        text: 'text-green-400',
        glow: 'shadow-green-500/20',
      };
    }
  };

  const colors = getColorClasses(percentage);

  // SVG circle properties
  const size = 200;
  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  // Metrics to display
  const metrics = [
    {
      icon: CheckCircle2,
      label: 'Tasks Completed',
      value: progressData.tasksCompleted,
      testId: 'tasks-completed',
    },
    {
      icon: FileText,
      label: 'Files Modified',
      value: progressData.filesModified,
      testId: 'files-modified',
    },
    {
      icon: FlaskConical,
      label: 'Tests Completed',
      value: progressData.testsCompleted,
      testId: 'tests-completed',
    },
  ];

  return (
    <div
      className="flex flex-col items-center justify-center p-6 bg-gray-900 border border-gray-800 rounded-lg"
      data-testid="progress-ring-container"
    >
      {/* SVG Circular Progress Ring */}
      <div className="relative flex items-center justify-center mb-6" data-testid="progress-ring">
        <svg
          width={size}
          height={size}
          className={cn('transform -rotate-90 transition-all duration-500', colors.glow)}
          data-testid="progress-svg"
        >
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="none"
            className="text-gray-800"
            data-testid="background-circle"
          />
          {/* Progress circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
            className={cn(colors.stroke, 'transition-all duration-1000 ease-out')}
            style={{
              strokeDasharray: circumference,
              strokeDashoffset: offset,
            }}
            data-testid="progress-circle"
          />
        </svg>

        {/* Percentage in center */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center"
          data-testid="percentage-display"
        >
          <span className={cn('text-5xl font-bold transition-colors duration-500', colors.text)}>
            {percentage}
          </span>
          <span className="text-2xl text-gray-400">%</span>
        </div>
      </div>

      {/* Metrics Display */}
      <div className="w-full space-y-3" data-testid="metrics-container">
        {metrics.map((metric) => {
          if (metric.value === undefined || metric.value === null) return null;

          const Icon = metric.icon;
          return (
            <div
              key={metric.testId}
              className="flex items-center justify-between px-4 py-2 bg-gray-800/50 rounded-lg border border-gray-700/50 transition-all duration-300 hover:border-gray-600"
              data-testid={metric.testId}
            >
              <div className="flex items-center gap-3">
                <Icon className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-300">{metric.label}</span>
              </div>
              <span className="text-sm font-semibold text-gray-100">{metric.value}</span>
            </div>
          );
        })}
      </div>

      {/* Optional Label */}
      {progressData.label && (
        <div
          className="mt-4 text-sm text-gray-400 text-center"
          data-testid="progress-label"
        >
          {progressData.label}
        </div>
      )}
    </div>
  );
}
