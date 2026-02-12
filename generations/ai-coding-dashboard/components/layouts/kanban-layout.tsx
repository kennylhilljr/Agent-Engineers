'use client';

import { useState } from 'react';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Task } from '@/db/schema';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

interface KanbanLayoutProps {
  tasks: Task[];
  currentTaskId?: number;
  onTaskUpdate?: (task: Task, newStatus: string) => Promise<void>;
}

interface KanbanColumn {
  id: string;
  title: string;
  status: string;
  tasks: Task[];
}

const statusColors = {
  todo: 'bg-gray-600',
  in_progress: 'bg-blue-600 animate-pulse',
  done: 'bg-green-600',
  blocked: 'bg-red-600',
};

const statusLabels = {
  todo: 'To Do',
  in_progress: 'In Progress',
  done: 'Done',
  blocked: 'Blocked',
};

function SortableTaskCard({ task, isCurrent }: { task: Task; isCurrent: boolean }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id.toString() });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const statusColor = statusColors[task.status as keyof typeof statusColors] || 'bg-gray-600';
  const statusLabel = statusLabels[task.status as keyof typeof statusLabels] || task.status;

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <Card
        className={`p-4 cursor-grab active:cursor-grabbing transition-all duration-300 ${
          isCurrent ? 'ring-2 ring-blue-500 shadow-lg' : ''
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline" className="text-xs">
                {task.category}
              </Badge>
              {isCurrent && (
                <Badge className="bg-blue-600 text-xs">Current</Badge>
              )}
            </div>
            <p className="text-sm text-gray-200">{task.description}</p>

            {/* Steps preview */}
            {Array.isArray(task.steps) && task.steps.length > 0 && (
              <div className="mt-2 text-xs text-gray-400">
                {task.steps.length} step{task.steps.length !== 1 ? 's' : ''}
              </div>
            )}
          </div>
          <Badge className={statusColor}>
            {statusLabel}
          </Badge>
        </div>
      </Card>
    </div>
  );
}

export function KanbanLayout({ tasks, currentTaskId, onTaskUpdate }: KanbanLayoutProps) {
  // Organize tasks into columns
  const initialColumns: KanbanColumn[] = [
    { id: 'todo', title: 'To Do', status: 'todo', tasks: [] },
    { id: 'in_progress', title: 'In Progress', status: 'in_progress', tasks: [] },
    { id: 'done', title: 'Done', status: 'done', tasks: [] },
    { id: 'blocked', title: 'Blocked', status: 'blocked', tasks: [] },
  ];

  // Group tasks by status
  const columns = initialColumns.map(col => ({
    ...col,
    tasks: tasks
      .filter(t => t.status === col.status)
      .sort((a, b) => a.order - b.order),
  }));

  const [activeTask, setActiveTask] = useState<Task | null>(null);

  // Configure sensors for drag and drop
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    const task = tasks.find(t => t.id.toString() === event.active.id);
    if (task) {
      setActiveTask(task);
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveTask(null);

    if (!over) return;

    const activeId = active.id.toString();
    const overId = over.id.toString();

    // Find the task being dragged
    const activeTask = tasks.find(t => t.id.toString() === activeId);
    if (!activeTask) return;

    // Determine target status
    let targetStatus = activeTask.status;

    // Check if dropped on a column
    const targetColumn = columns.find(col => col.id === overId);
    if (targetColumn) {
      targetStatus = targetColumn.status;
    } else {
      // Dropped on another task - find its column
      const targetTask = tasks.find(t => t.id.toString() === overId);
      if (targetTask) {
        targetStatus = targetTask.status;
      }
    }

    // Update task status if changed
    if (targetStatus !== activeTask.status && onTaskUpdate) {
      await onTaskUpdate({ ...activeTask, status: targetStatus }, targetStatus);
    }
  };

  // Calculate stats
  const stats = {
    total: tasks.length,
    todo: tasks.filter(t => t.status === 'todo').length,
    in_progress: tasks.filter(t => t.status === 'in_progress').length,
    done: tasks.filter(t => t.status === 'done').length,
    blocked: tasks.filter(t => t.status === 'blocked').length,
  };

  const progressPercent = stats.total > 0 ? (stats.done / stats.total) * 100 : 0;

  return (
    <div className="h-full p-8">
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2">Kanban Board</h2>
        <p className="text-gray-400 mb-4">
          Drag tasks to reorder or change status
        </p>

        {/* Progress */}
        <div className="bg-gray-800 rounded-full h-3 overflow-hidden mb-2">
          <div
            className="bg-gradient-to-r from-blue-500 to-green-500 h-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="flex gap-4 text-sm text-gray-400">
          <span>{stats.done} of {stats.total} completed</span>
          <span>{Math.round(progressPercent)}%</span>
        </div>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {columns.map(column => (
            <div
              key={column.id}
              id={column.id}
              className="bg-gray-800 rounded-lg p-4 min-h-[500px]"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold">{column.title}</h3>
                <Badge variant="secondary" className="ml-2">
                  {column.tasks.length}
                </Badge>
              </div>

              <SortableContext
                items={column.tasks.map(t => t.id.toString())}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-3">
                  {column.tasks.map(task => (
                    <SortableTaskCard
                      key={task.id}
                      task={task}
                      isCurrent={task.id === currentTaskId}
                    />
                  ))}
                  {column.tasks.length === 0 && (
                    <div className="text-gray-500 text-sm italic text-center py-8 border-2 border-dashed border-gray-700 rounded-lg">
                      Drop tasks here
                    </div>
                  )}
                </div>
              </SortableContext>
            </div>
          ))}
        </div>

        <DragOverlay>
          {activeTask ? (
            <div className="opacity-80">
              <SortableTaskCard task={activeTask} isCurrent={false} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
