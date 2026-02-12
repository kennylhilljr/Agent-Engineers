import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, tasks, activityLog } from '@/db/schema';
import { eq, desc } from 'drizzle-orm';
import {
  successResponse,
  errorResponse,
  type ExecutionResponse,
} from '@/lib/api-types';

/**
 * GET /api/projects/[projectId]/status
 * Get current execution status for a project
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const projectId = parseInt(params.projectId, 10);
    if (isNaN(projectId)) {
      return NextResponse.json(
        errorResponse('Invalid project ID', 'Project ID must be a number'),
        { status: 400 }
      );
    }

    // Check if project exists
    const [project] = await db
      .select()
      .from(projects)
      .where(eq(projects.id, projectId));

    if (!project) {
      return NextResponse.json(
        errorResponse('Project not found', `No project found with ID ${projectId}`),
        { status: 404 }
      );
    }

    // Get task statistics
    const projectTasks = await db
      .select()
      .from(tasks)
      .where(eq(tasks.projectId, projectId));

    const totalTasks = projectTasks.length;
    const completedTasks = projectTasks.filter((t) => t.status === 'done').length;
    const inProgressTasks = projectTasks.filter((t) => t.status === 'in_progress').length;
    const progress = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

    // Find the most recent execution event
    const executionEvents = await db
      .select()
      .from(activityLog)
      .where(eq(activityLog.projectId, projectId))
      .orderBy(desc(activityLog.timestamp))
      .limit(10);

    // Determine current status from events
    let status: 'idle' | 'running' | 'paused' | 'stopped' | 'completed' | 'error' = 'idle';
    let startedAt: string | undefined;
    let pausedAt: string | undefined;
    let stoppedAt: string | undefined;
    let completedAt: string | undefined;
    let currentTaskId: number | undefined;

    for (const event of executionEvents) {
      if (event.eventType === 'execution_started') {
        status = 'running';
        startedAt = event.timestamp.toISOString();
        currentTaskId = event.eventData.startTaskId;
        break;
      } else if (event.eventType === 'execution_paused') {
        status = 'paused';
        pausedAt = event.timestamp.toISOString();
        break;
      } else if (event.eventType === 'execution_stopped') {
        status = 'stopped';
        stoppedAt = event.timestamp.toISOString();
        break;
      } else if (event.eventType === 'execution_completed') {
        status = 'completed';
        completedAt = event.timestamp.toISOString();
        break;
      } else if (event.eventType === 'error') {
        status = 'error';
        break;
      }
    }

    // If all tasks are done, status is completed
    if (totalTasks > 0 && completedTasks === totalTasks && status === 'idle') {
      status = 'completed';
    }

    const response: ExecutionResponse = {
      status,
      currentTaskId,
      startedAt,
      pausedAt,
      stoppedAt,
      completedAt,
      progress,
      message: `Project "${project.name}" is ${status}. ${completedTasks}/${totalTasks} tasks completed.`,
    };

    return NextResponse.json(successResponse(response));
  } catch (error) {
    console.error('Error fetching execution status:', error);
    return NextResponse.json(
      errorResponse('Failed to fetch execution status', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
