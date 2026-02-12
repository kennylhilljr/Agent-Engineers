"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TaskResponse } from "@/lib/api-types";
import { GripVertical } from "lucide-react";

interface TaskCardProps {
  task: TaskResponse;
  isLoading?: boolean;
  isDragging?: boolean;
}

export function TaskCard({ task, isLoading, isDragging }: TaskCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging: isSortableDragging,
  } = useSortable({ id: task.id.toString() });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging || isSortableDragging ? 0.5 : 1,
    cursor: isLoading ? "wait" : "grab",
  };

  // Get category color
  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      frontend: "bg-blue-600",
      backend: "bg-green-600",
      testing: "bg-yellow-600",
      deployment: "bg-purple-600",
      documentation: "bg-pink-600",
      general: "bg-gray-600",
    };
    return colors[category.toLowerCase()] || colors.general;
  };

  return (
    <Card
      ref={setNodeRef}
      style={style}
      className={`bg-gray-700 border-gray-600 hover:border-gray-500 transition-colors ${
        isLoading ? "pointer-events-none" : ""
      }`}
    >
      <div className="p-4">
        <div className="flex items-start gap-2 mb-2">
          <div
            {...attributes}
            {...listeners}
            className="mt-1 cursor-grab active:cursor-grabbing"
            aria-label="Drag handle"
          >
            <GripVertical className="w-4 h-4 text-gray-400" />
          </div>
          <div className="flex-1">
            <div className="flex items-start justify-between gap-2 mb-2">
              <h3 className="font-medium text-sm leading-tight flex-1">
                {task.description}
              </h3>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge
                className={`${getCategoryColor(task.category)} text-white text-xs`}
              >
                {task.category}
              </Badge>
              {task.steps && task.steps.length > 0 && (
                <span className="text-xs text-gray-400">
                  {task.steps.length} steps
                </span>
              )}
            </div>
            {task.agentNotes && (
              <p className="text-xs text-gray-400 mt-2 line-clamp-2">
                {task.agentNotes}
              </p>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
