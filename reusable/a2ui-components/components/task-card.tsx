import React from 'react';
import { A2UIProps, TaskCardData } from '@/lib/a2ui-types';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import {
  CheckCircle2,
  Circle,
  Clock,
  XCircle,
  Settings,
  Database,
  Layout,
  Box,
  Sparkles,
  FlaskConical,
  Palette,
  Calendar,
  User
} from 'lucide-react';

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'blocked';
export type TaskCategory = 'setup' | 'backend' | 'frontend' | 'a2ui-catalog' | 'feature' | 'testing' | 'styling';

const statusConfig: Record<TaskStatus, {
  color: string;
  bgColor: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>
}> = {
  pending: {
    color: 'text-gray-400',
    bgColor: 'bg-gray-500/10 border-gray-500/20',
    label: 'Pending',
    icon: Circle
  },
  in_progress: {
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10 border-blue-500/20',
    label: 'In Progress',
    icon: Clock
  },
  completed: {
    color: 'text-green-400',
    bgColor: 'bg-green-500/10 border-green-500/20',
    label: 'Completed',
    icon: CheckCircle2
  },
  blocked: {
    color: 'text-red-400',
    bgColor: 'bg-red-500/10 border-red-500/20',
    label: 'Blocked',
    icon: XCircle
  },
};

const categoryConfig: Record<TaskCategory, {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  color: string;
}> = {
  setup: { icon: Settings, label: 'Setup', color: 'text-purple-400' },
  backend: { icon: Database, label: 'Backend', color: 'text-orange-400' },
  frontend: { icon: Layout, label: 'Frontend', color: 'text-cyan-400' },
  'a2ui-catalog': { icon: Box, label: 'A2UI Catalog', color: 'text-pink-400' },
  feature: { icon: Sparkles, label: 'Feature', color: 'text-yellow-400' },
  testing: { icon: FlaskConical, label: 'Testing', color: 'text-green-400' },
  styling: { icon: Palette, label: 'Styling', color: 'text-indigo-400' },
};

/**
 * TaskCard - Displays task information with status, category, and progress
 * Fully implemented A2UI component with dark theme
 */
export function TaskCard({ type, data, metadata, onEvent }: A2UIProps) {
  const taskData = data as TaskCardData;
  const status = taskData.status || 'pending';
  const category = taskData.category;
  const progress = taskData.progress ?? 0;

  const StatusIcon = statusConfig[status]?.icon || Circle;
  const CategoryIcon = category ? categoryConfig[category]?.icon : null;

  const handleViewDetails = () => {
    if (onEvent) {
      onEvent('click' as any, { action: 'view_details', taskData });
    }
  };

  return (
    <Card
      className={cn(
        "bg-gray-900 border-gray-800 text-gray-100 hover:border-blue-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10",
        "cursor-pointer"
      )}
      onClick={handleViewDetails}
      data-testid="task-card"
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-lg font-semibold text-gray-100 flex-1">
            {taskData.title || 'Untitled Task'}
          </CardTitle>
          <Badge
            className={cn(
              "flex items-center gap-1.5 px-2 py-1",
              statusConfig[status].bgColor,
              statusConfig[status].color,
              "border transition-all duration-200"
            )}
            data-testid="status-badge"
          >
            <StatusIcon className="w-3 h-3" />
            <span className="text-xs font-medium">{statusConfig[status].label}</span>
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Category Badge */}
        {category && CategoryIcon && (
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={cn(
                "flex items-center gap-1.5 px-2 py-1 bg-gray-800/50 border-gray-700",
                categoryConfig[category].color
              )}
              data-testid="category-badge"
            >
              <CategoryIcon className="w-3 h-3" />
              <span className="text-xs">{categoryConfig[category].label}</span>
            </Badge>
          </div>
        )}

        {/* Description */}
        {taskData.description && (
          <p className="text-sm text-gray-400 line-clamp-2" data-testid="task-description">
            {taskData.description}
          </p>
        )}

        {/* Progress Bar */}
        {progress > 0 && (
          <div className="space-y-1" data-testid="progress-container">
            <div className="flex items-center justify-between text-xs text-gray-400">
              <span>Progress</span>
              <span className="font-medium text-blue-400">{progress}%</span>
            </div>
            <Progress
              value={progress}
              className="h-2 bg-gray-800"
              data-testid="progress-bar"
            />
          </div>
        )}

        {/* Metadata Row */}
        <div className="flex items-center gap-4 text-xs text-gray-500 pt-1">
          {taskData.assignee && (
            <div className="flex items-center gap-1.5" data-testid="assignee">
              <User className="w-3 h-3" />
              <span>{taskData.assignee}</span>
            </div>
          )}
          {taskData.dueDate && (
            <div className="flex items-center gap-1.5" data-testid="due-date">
              <Calendar className="w-3 h-3" />
              <span>{new Date(taskData.dueDate).toLocaleDateString()}</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
