'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Task } from '@/db/schema';
import { Check, Circle, AlertCircle, Ban } from 'lucide-react';

interface TimelineLayoutProps {
  tasks: Task[];
  currentTaskId?: number;
}

const statusColors = {
  todo: 'bg-gray-500',
  in_progress: 'bg-blue-500',
  done: 'bg-green-500',
  blocked: 'bg-red-500',
};

const statusIcons = {
  todo: Circle,
  in_progress: Circle,
  done: Check,
  blocked: Ban,
};

const statusLabels = {
  todo: 'To Do',
  in_progress: 'In Progress',
  done: 'Done',
  blocked: 'Blocked',
};

export function TimelineLayout({ tasks, currentTaskId }: TimelineLayoutProps) {
  // Sort tasks by order
  const sortedTasks = [...tasks].sort((a, b) => a.order - b.order);

  // Calculate progress
  const completedCount = tasks.filter(t => t.status === 'done').length;
  const totalCount = tasks.length;
  const progressPercent = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  return (
    <div className="max-w-5xl mx-auto p-8">
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2">Project Timeline</h2>
        <p className="text-gray-400 mb-4">
          Sequential task workflow showing progress and dependencies
        </p>

        {/* Progress Bar */}
        <div className="bg-gray-800 rounded-full h-3 overflow-hidden">
          <div
            className="bg-gradient-to-r from-blue-500 to-green-500 h-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-sm text-gray-400">
          <span>{completedCount} of {totalCount} completed</span>
          <span>{Math.round(progressPercent)}%</span>
        </div>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gray-700" />

        {/* Tasks */}
        <div className="space-y-6">
          {sortedTasks.map((task, index) => {
            const isCurrent = task.id === currentTaskId;
            const StatusIcon = statusIcons[task.status as keyof typeof statusIcons] || Circle;
            const statusColor = statusColors[task.status as keyof typeof statusColors] || 'bg-gray-500';

            return (
              <div key={task.id} className="relative flex items-start gap-6">
                {/* Timeline marker */}
                <div className={`relative z-10 flex-shrink-0 w-12 h-12 rounded-full border-4 border-gray-900 ${statusColor} flex items-center justify-center`}>
                  <StatusIcon className="w-6 h-6 text-white" />
                </div>

                {/* Task card */}
                <Card
                  className={`flex-1 p-6 transition-all duration-300 ${
                    isCurrent
                      ? 'ring-2 ring-blue-500 shadow-xl shadow-blue-500/20 scale-[1.02]'
                      : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-mono text-gray-400">
                          #{index + 1}
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {task.category}
                        </Badge>
                        {isCurrent && (
                          <Badge className="bg-blue-600">Current</Badge>
                        )}
                      </div>
                      <h3 className="text-lg font-semibold text-white mb-1">
                        {task.description}
                      </h3>
                    </div>
                    <Badge className={statusColor}>
                      {statusLabels[task.status as keyof typeof statusLabels] || task.status}
                    </Badge>
                  </div>

                  {/* Steps */}
                  {Array.isArray(task.steps) && task.steps.length > 0 && (
                    <div className="mt-4 pl-4 border-l-2 border-gray-700">
                      <p className="text-xs text-gray-400 mb-2">Implementation Steps:</p>
                      <ul className="space-y-1">
                        {task.steps.map((step, stepIndex) => (
                          <li
                            key={stepIndex}
                            className="text-sm text-gray-300 flex items-start gap-2"
                          >
                            <span className="text-gray-500 mt-1">•</span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Agent Notes */}
                  {task.agentNotes && (
                    <div className="mt-4 p-3 bg-gray-800/50 rounded-lg border border-gray-700">
                      <p className="text-xs text-gray-400 mb-1">Agent Notes:</p>
                      <p className="text-sm text-gray-300">{task.agentNotes}</p>
                    </div>
                  )}
                </Card>
              </div>
            );
          })}
        </div>
      </div>

      {/* Summary */}
      <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4">
        {Object.entries(statusLabels).map(([status, label]) => {
          const count = tasks.filter(t => t.status === status).length;
          const color = statusColors[status as keyof typeof statusColors];

          return (
            <Card key={status} className="p-4">
              <div className="flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full ${color}`} />
                <div>
                  <p className="text-2xl font-bold">{count}</p>
                  <p className="text-xs text-gray-400">{label}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
