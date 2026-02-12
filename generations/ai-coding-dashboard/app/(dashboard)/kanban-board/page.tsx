"use client";

import { useState, useEffect, useCallback } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useCopilotContext } from "@copilotkit/react-core";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TaskCard } from "./task-card";
import { Task, TaskResponse } from "@/lib/api-types";

interface KanbanColumn {
  id: string;
  title: string;
  status: "todo" | "in_progress" | "done" | "blocked";
  tasks: TaskResponse[];
}

export default function KanbanBoardPage() {
  const [projectId, setProjectId] = useState<number>(1); // Default to project 1
  const [columns, setColumns] = useState<KanbanColumn[]>([
    { id: "todo", title: "To Do", status: "todo", tasks: [] },
    { id: "in_progress", title: "In Progress", status: "in_progress", tasks: [] },
    { id: "done", title: "Done", status: "done", tasks: [] },
    { id: "blocked", title: "Blocked", status: "blocked", tasks: [] },
  ]);
  const [activeTask, setActiveTask] = useState<TaskResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Access CopilotKit context for AG-UI state updates
  const copilotContext = useCopilotContext();

  // Configure sensors for drag and drop
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // Minimum drag distance before activating
      },
    })
  );

  // Fetch tasks from API
  const fetchTasks = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/projects/${projectId}/tasks`);
      if (!response.ok) {
        throw new Error("Failed to fetch tasks");
      }

      const result = await response.json();
      if (result.success) {
        // Organize tasks into columns by status
        const tasksByStatus: Record<string, TaskResponse[]> = {
          todo: [],
          in_progress: [],
          done: [],
          blocked: [],
        };

        result.data.forEach((task: TaskResponse) => {
          if (tasksByStatus[task.status]) {
            tasksByStatus[task.status].push(task);
          }
        });

        // Sort tasks within each column by order field
        Object.keys(tasksByStatus).forEach((status) => {
          tasksByStatus[status].sort((a, b) => a.order - b.order);
        });

        // Update columns with fetched tasks
        setColumns([
          { id: "todo", title: "To Do", status: "todo", tasks: tasksByStatus.todo },
          { id: "in_progress", title: "In Progress", status: "in_progress", tasks: tasksByStatus.in_progress },
          { id: "done", title: "Done", status: "done", tasks: tasksByStatus.done },
          { id: "blocked", title: "Blocked", status: "blocked", tasks: tasksByStatus.blocked },
        ]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      console.error("Error fetching tasks:", err);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  // Fetch tasks on mount and when projectId changes
  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Send task order update to backend and AG-UI
  const updateTaskOrder = async (updatedTasks: TaskResponse[]) => {
    setIsLoading(true);
    setError(null);

    try {
      // Send batch update to backend
      const response = await fetch(`/api/projects/${projectId}/tasks/reorder`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          taskOrder: updatedTasks.map((task, index) => ({
            id: task.id,
            order: index,
            status: task.status,
          })),
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to update task order");
      }

      const result = await response.json();

      if (result.success) {
        // Emit AG-UI state update via CopilotKit
        // This allows the agent to receive and adapt to the new task priority
        if (copilotContext) {
          try {
            // Send state update event to agent
            await fetch(`/api/projects/${projectId}/events`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                eventType: "task_reordered",
                eventData: {
                  taskOrder: updatedTasks.map((t) => ({
                    id: t.id,
                    description: t.description,
                    status: t.status,
                    order: t.order,
                  })),
                  reorderedAt: new Date().toISOString(),
                },
                agentReasoning: "User reordered tasks via drag-and-drop in kanban board",
              }),
            });
          } catch (agUiError) {
            console.warn("AG-UI state update failed (non-fatal):", agUiError);
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      console.error("Error updating task order:", err);
      // Revert to previous state by refetching
      fetchTasks();
    } finally {
      setIsLoading(false);
    }
  };

  // Handle drag start
  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    const task = columns
      .flatMap((col) => col.tasks)
      .find((t) => t.id.toString() === active.id);

    if (task) {
      setActiveTask(task);
    }
  };

  // Handle drag end
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveTask(null);

    if (!over) return;

    const activeId = active.id.toString();
    const overId = over.id.toString();

    // Find which column the active task is in
    const activeColumn = columns.find((col) =>
      col.tasks.some((t) => t.id.toString() === activeId)
    );

    // Find which column we're dropping into
    // overId could be a task ID or a column ID
    let targetColumn = columns.find((col) => col.id === overId);
    if (!targetColumn) {
      targetColumn = columns.find((col) =>
        col.tasks.some((t) => t.id.toString() === overId)
      );
    }

    if (!activeColumn || !targetColumn) return;

    const activeTask = activeColumn.tasks.find(
      (t) => t.id.toString() === activeId
    );
    if (!activeTask) return;

    // If dragging within the same column
    if (activeColumn.id === targetColumn.id) {
      const oldIndex = activeColumn.tasks.findIndex(
        (t) => t.id.toString() === activeId
      );
      const newIndex = activeColumn.tasks.findIndex(
        (t) => t.id.toString() === overId
      );

      if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
        const reorderedTasks = arrayMove(
          activeColumn.tasks,
          oldIndex,
          newIndex
        );

        // Update column with reordered tasks
        const updatedColumns = columns.map((col) =>
          col.id === activeColumn.id ? { ...col, tasks: reorderedTasks } : col
        );

        setColumns(updatedColumns);

        // Send update to backend
        updateTaskOrder(reorderedTasks);
      }
    } else {
      // Moving task to a different column (status change)
      const updatedTask = { ...activeTask, status: targetColumn.status };

      // Remove from old column
      const newActiveColumnTasks = activeColumn.tasks.filter(
        (t) => t.id.toString() !== activeId
      );

      // Add to new column
      const newTargetColumnTasks = [...targetColumn.tasks, updatedTask];

      // Update columns
      const updatedColumns = columns.map((col) => {
        if (col.id === activeColumn.id) {
          return { ...col, tasks: newActiveColumnTasks };
        }
        if (col.id === targetColumn.id) {
          return { ...col, tasks: newTargetColumnTasks };
        }
        return col;
      });

      setColumns(updatedColumns);

      // Send update to backend (includes all tasks from both affected columns)
      updateTaskOrder([...newActiveColumnTasks, ...newTargetColumnTasks]);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">Kanban Board</h1>
          <p className="text-gray-400">
            Drag tasks to reorder priorities or change status
          </p>
          {error && (
            <div className="mt-4 p-4 bg-red-900/20 border border-red-500 rounded-lg text-red-200">
              {error}
            </div>
          )}
        </div>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {columns.map((column) => (
              <div
                key={column.id}
                className="bg-gray-800 rounded-lg p-4 min-h-[400px]"
              >
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold">{column.title}</h2>
                  <Badge variant="secondary" className="ml-2">
                    {column.tasks.length}
                  </Badge>
                </div>

                <SortableContext
                  items={column.tasks.map((t) => t.id.toString())}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="space-y-3">
                    {column.tasks.map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        isLoading={isLoading}
                      />
                    ))}
                    {column.tasks.length === 0 && (
                      <div
                        id={column.id}
                        className="text-gray-500 text-sm italic text-center py-8 border-2 border-dashed border-gray-700 rounded-lg"
                      >
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
                <TaskCard task={activeTask} isLoading={false} isDragging />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>

        {isLoading && (
          <div className="fixed bottom-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg">
            Updating tasks...
          </div>
        )}
      </div>
    </div>
  );
}
