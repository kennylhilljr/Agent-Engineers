import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, tasks, activityLog } from '@/db/schema';
import { eq } from 'drizzle-orm';
import {
  StartExecutionSchema,
  successResponse,
  errorResponse,
  type ExecutionResponse,
} from '@/lib/api-types';

/**
 * POST /api/projects/[projectId]/start
 * Start agent execution for a project
 */
export async function POST(
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

    const body = await request.json();

    // Validate request body
    const validation = StartExecutionSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        errorResponse('Invalid request body', validation.error.errors),
        { status: 400 }
      );
    }

    const { taskId, autoApprove, config } = validation.data;

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

    // If taskId is specified, verify it exists
    if (taskId) {
      const [task] = await db
        .select()
        .from(tasks)
        .where(eq(tasks.id, taskId));

      if (!task || task.projectId !== projectId) {
        return NextResponse.json(
          errorResponse('Task not found', `No task found with ID ${taskId} in project ${projectId}`),
          { status: 404 }
        );
      }
    }

    // Get project statistics
    const projectTasks = await db
      .select()
      .from(tasks)
      .where(eq(tasks.projectId, projectId));

    const totalTasks = projectTasks.length;
    const completedTasks = projectTasks.filter((t) => t.status === 'done').length;
    const progress = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

    // Log execution start event
    await db.insert(activityLog).values({
      projectId,
      eventType: 'execution_started',
      eventData: {
        startTaskId: taskId,
        autoApprove: autoApprove || false,
        config: config || {},
        totalTasks,
        completedTasks,
      },
      agentReasoning: `Execution started for project "${project.name}"${taskId ? ` from task ${taskId}` : ''}`,
    });

    const response: ExecutionResponse = {
      status: 'running',
      currentTaskId: taskId,
      startedAt: new Date().toISOString(),
      progress,
      message: `Execution started for project "${project.name}"`,
    };

    return NextResponse.json(
      successResponse(response, 'Execution started successfully'),
      { status: 200 }
    );
  } catch (error) {
    console.error('Error starting execution:', error);
    return NextResponse.json(
      errorResponse('Failed to start execution', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
