"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FileEdit, TestTube, GitBranch, AlertCircle, CheckCircle } from "lucide-react";

export interface ActivityEvent {
  id: string;
  type: "file_modified" | "test_run" | "approval_requested" | "task_completed" | "error";
  title: string;
  description?: string;
  timestamp: Date;
  agentReasoning?: string;
}

interface ActivityFeedProps {
  events: ActivityEvent[];
  maxHeight?: string;
}

const eventIcons = {
  file_modified: FileEdit,
  test_run: TestTube,
  approval_requested: AlertCircle,
  task_completed: CheckCircle,
  error: AlertCircle,
};

const eventColors = {
  file_modified: "text-blue-500",
  test_run: "text-green-500",
  approval_requested: "text-yellow-500",
  task_completed: "text-emerald-500",
  error: "text-red-500",
};

const eventBadgeVariants = {
  file_modified: "secondary",
  test_run: "default",
  approval_requested: "outline",
  task_completed: "default",
  error: "destructive",
} as const;

function formatTimestamp(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

export function ActivityFeed({ events, maxHeight = "600px" }: ActivityFeedProps) {
  return (
    <Card className="w-full h-full flex flex-col">
      <CardHeader>
        <CardTitle className="text-lg">Activity Feed</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-full" style={{ maxHeight }}>
          <div className="px-6 pb-6 space-y-4">
            {events.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                No activity yet
              </div>
            ) : (
              events.map((event) => {
                const Icon = eventIcons[event.type];
                const iconColor = eventColors[event.type];
                const badgeVariant = eventBadgeVariants[event.type];

                return (
                  <div
                    key={event.id}
                    className="flex gap-3 p-3 rounded-lg hover:bg-secondary/50 transition-colors"
                  >
                    <div className={`flex-shrink-0 mt-1 ${iconColor}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h4 className="text-sm font-medium">{event.title}</h4>
                        <Badge variant={badgeVariant} className="text-xs flex-shrink-0">
                          {event.type.replace(/_/g, " ")}
                        </Badge>
                      </div>
                      {event.description && (
                        <p className="text-sm text-muted-foreground mb-2">
                          {event.description}
                        </p>
                      )}
                      {event.agentReasoning && (
                        <div className="text-xs text-muted-foreground bg-secondary/30 p-2 rounded border-l-2 border-primary/50 mb-2">
                          <span className="font-medium">Agent:</span> {event.agentReasoning}
                        </div>
                      )}
                      <div className="text-xs text-muted-foreground">
                        {formatTimestamp(event.timestamp)}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
