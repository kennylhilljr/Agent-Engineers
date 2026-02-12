import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, tasks, activityLog } from '@/db/schema';
import { eq, and } from 'drizzle-orm';
import {
  CompleteTaskSchema,
  successResponse,
  errorResponse,
  type TaskResponse,
} from '@/lib/api-types';

/**
 * POST /api/projects/[projectId]/tasks/[taskId]/complete
 * Mark a task as completed
 */
export async function POST(
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
    const validation = CompleteTaskSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        errorResponse('Invalid request body', validation.error.errors),
        { status: 400 }
      );
    }

    const { success, notes, filesChanged } = validation.data;

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

    // Check if task is already completed
    if (existingTask.status === 'done') {
      return NextResponse.json(
        errorResponse('Task already completed', 'This task is already marked as done'),
        { status: 400 }
      );
    }

    // Update task status and notes
    const newStatus = success ? 'done' : 'blocked';
    const agentNotes = notes
      ? `${existingTask.agentNotes || ''}\n\nCompletion notes: ${notes}`.trim()
      : existingTask.agentNotes;

    const [updatedTask] = await db
      .update(tasks)
      .set({
        status: newStatus,
        agentNotes,
      })
      .where(eq(tasks.id, taskId))
      .returning();

    // Log the completion event
    await db.insert(activityLog).values({
      projectId,
      eventType: 'task_completed',
      eventData: {
        taskId,
        taskName: existingTask.description,
        success,
        filesChanged: filesChanged || [],
        previousStatus: existingTask.status,
        newStatus,
      },
      agentReasoning: notes || `Task ${success ? 'completed successfully' : 'blocked'}`,
    });

    const response: TaskResponse = updatedTask;

    return NextResponse.json(
      successResponse(
        response,
        success ? 'Task completed successfully' : 'Task marked as blocked'
      )
    );
  } catch (error) {
    console.error('Error completing task:', error);
    return NextResponse.json(
      errorResponse('Failed to complete task', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
