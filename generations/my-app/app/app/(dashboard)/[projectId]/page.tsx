"use client";

import React, { useState, useEffect } from "react";
import { DashboardHeader } from "@/components/dashboard/header";
import { ActivityFeed, ActivityEvent } from "@/components/dashboard/activity-feed";
import { ComponentContainer } from "@/components/dashboard/component-container";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MessageSquare } from "lucide-react";

interface DashboardPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export default function DashboardPage({ params }: DashboardPageProps) {
  const [projectId, setProjectId] = useState<string>("");
  const [projectData, setProjectData] = useState({
    name: "AI Coding Dashboard",
    completionPercentage: 35,
    tasksDone: 7,
    tasksTotal: 20,
    filesModified: 42,
    testsPassed: 156,
    testsTotal: 200,
  });

  const [activityEvents, setActivityEvents] = useState<ActivityEvent[]>([
    {
      id: "1",
      type: "task_completed",
      title: "Database schema created",
      description: "Created tables for projects, tasks, and files",
      timestamp: new Date(Date.now() - 1000 * 60 * 15),
      agentReasoning: "Set up PostgreSQL schema with Drizzle ORM for efficient data management",
    },
    {
      id: "2",
      type: "test_run",
      title: "Unit tests passed",
      description: "All 24 component tests passing",
      timestamp: new Date(Date.now() - 1000 * 60 * 30),
    },
    {
      id: "3",
      type: "file_modified",
      title: "Updated API routes",
      description: "Modified /api/ag-ui/route.ts",
      timestamp: new Date(Date.now() - 1000 * 60 * 45),
      agentReasoning: "Added streaming support for real-time agent communication",
    },
    {
      id: "4",
      type: "approval_requested",
      title: "Approval needed for deployment",
      description: "Ready to deploy to staging",
      timestamp: new Date(Date.now() - 1000 * 60 * 60),
    },
  ]);

  const [a2uiComponents, setA2uiComponents] = useState<React.ReactNode[]>([]);
  const [isLoadingComponents, setIsLoadingComponents] = useState(false);
  const [componentError, setComponentError] = useState<string | null>(null);

  useEffect(() => {
    params.then((resolvedParams) => {
      setProjectId(resolvedParams.projectId);
      // In production, fetch project data based on projectId
      // For now, using mock data
    });
  }, [params]);

  return (
    <div className="space-y-6">
      {/* Project Header */}
      <DashboardHeader
        projectName={projectData.name}
        completionPercentage={projectData.completionPercentage}
        tasksDone={projectData.tasksDone}
        tasksTotal={projectData.tasksTotal}
        filesModified={projectData.filesModified}
        testsPassed={projectData.testsPassed}
        testsTotal={projectData.testsTotal}
      />

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content Area - 2 columns on large screens */}
        <div className="lg:col-span-2 space-y-6">
          {/* A2UI Component Container */}
          <ComponentContainer
            components={a2uiComponents}
            isLoading={isLoadingComponents}
            error={componentError}
          />
        </div>

        {/* Sidebar - 1 column on large screens */}
        <div className="space-y-6">
          {/* Chat Sidebar Placeholder */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <MessageSquare className="w-5 h-5" />
                Agent Chat
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground text-center py-8">
                CopilotKit chat interface will be integrated here
              </div>
            </CardContent>
          </Card>

          {/* Activity Feed */}
          <ActivityFeed events={activityEvents} maxHeight="500px" />
        </div>
      </div>
    </div>
  );
}
