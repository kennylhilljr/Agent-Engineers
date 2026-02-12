import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, tasks, activityLog } from '@/db/schema';
import { eq, and } from 'drizzle-orm';
import {
  UpdateTaskSchema,
  successResponse,
  errorResponse,
  type TaskResponse,
} from '@/lib/api-types';

/**
 * GET /api/projects/[projectId]/tasks/[taskId]
 * Get a specific task by ID
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { projectId: string; taskId: string } }
) {
  try {
    const projectId = parseInt(params.projectId, 10);
    const taskId = parseInt(params.taskId, 10);

    if (isNaN(projectId) || isNaN(taskId)) {
      return NextResponse.json(
        errorResponse('Invalid ID', 'Project ID and Task ID must be numbers'),
        { status: 400 }
      );
    }

    // Fetch the task
    const [task] = await db
      .select()
      .from(tasks)
      .where(and(eq(tasks.id, taskId), eq(tasks.projectId, projectId)));

    if (!task) {
      return NextResponse.json(
        errorResponse('Task not found', `No task found with ID ${taskId} in project ${projectId}`),
        { status: 404 }
      );
    }

    const response: TaskResponse = task;

    return NextResponse.json(successResponse(response));
  } catch (error) {
    console.error('Error fetching task:', error);
    return NextResponse.json(
      errorResponse('Failed to fetch task', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}

/**
 * PATCH /api/projects/[projectId]/tasks/[taskId]
 * Update a task
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: { projectId: string; taskId: string } }
) {
  try {
    const projectId = parseInt(params.projectId, 10);
    const taskId = parseInt(params.taskId, 10);

    if (isNaN(projectId) || isNaN(taskId)) {
      return NextResponse.json(
        errorResponse('Invalid ID', 'Project ID and Task ID must be numbers'),
        { status: 400 }
      );
    }

    const body = await request.json();

    // Validate request body
    const validation = UpdateTaskSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        errorResponse('Invalid request body', validation.error.errors),
        { status: 400 }
      );
    }

    // Check if task exists
    const [existingTask] = await db
      .select()
      .from(tasks)
      .where(and(eq(tasks.id, taskId), eq(tasks.projectId, projectId)));

    if (!existingTask) {
      return NextResponse.json(
        errorResponse('Task not found', `No task found with ID ${taskId} in project ${projectId}`),
        { status: 404 }
      );
    }

    // Update the task
    const [updatedTask] = await db
      .update(tasks)
      .set(validation.data)
      .where(eq(tasks.id, taskId))
      .returning();

    // Log the update event
    await db.insert(activityLog).values({
      projectId,
      eventType: 'task_updated',
      eventData: {
        taskId,
        changes: validation.data,
        previousStatus: existingTask.status,
        newStatus: updatedTask.status,
      },
      agentReasoning: `Task updated: ${updatedTask.description}`,
    });

    const response: TaskResponse = updatedTask;

    return NextResponse.json(successResponse(response, 'Task updated successfully'));
  } catch (error) {
    console.error('Error updating task:', error);
    return NextResponse.json(
      errorResponse('Failed to update task', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/projects/[projectId]/tasks/[taskId]
 * Delete a task
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: { projectId: string; taskId: string } }
) {
  try {
    const projectId = parseInt(params.projectId, 10);
    const taskId = parseInt(params.taskId, 10);

    if (isNaN(projectId) || isNaN(taskId)) {
      return NextResponse.json(
        errorResponse('Invalid ID', 'Project ID and Task ID must be numbers'),
        { status: 400 }
      );
    }

    // Check if task exists
    const [existingTask] = await db
      .select()
      .from(tasks)
      .where(and(eq(tasks.id, taskId), eq(tasks.projectId, projectId)));

    if (!existingTask) {
      return NextResponse.json(
        errorResponse('Task not found', `No task found with ID ${taskId} in project ${projectId}`),
        { status: 404 }
      );
    }

    // Delete the task
    await db.delete(tasks).where(eq(tasks.id, taskId));

    return NextResponse.json(
      successResponse({ id: taskId }, 'Task deleted successfully')
    );
  } catch (error) {
    console.error('Error deleting task:', error);
    return NextResponse.json(
      errorResponse('Failed to delete task', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
