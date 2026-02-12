import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, tasks, activityLog } from '@/db/schema';
import { eq, inArray } from 'drizzle-orm';
import { successResponse, errorResponse } from '@/lib/api-types';
import { z } from 'zod';

/**
 * Schema for reordering tasks
 */
const ReorderTasksSchema = z.object({
  taskOrder: z.array(
    z.object({
      id: z.number().int().positive(),
      order: z.number().int().nonnegative(),
      status: z.enum(['todo', 'in_progress', 'done', 'blocked']).optional(),
    })
  ).min(1, 'At least one task must be provided'),
});

type ReorderTasksRequest = z.infer<typeof ReorderTasksSchema>;

/**
 * POST /api/projects/[projectId]/tasks/reorder
 * Reorder tasks and optionally update their status
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
    const validation = ReorderTasksSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        errorResponse('Invalid request body', validation.error.errors),
        { status: 400 }
      );
    }

    const { taskOrder } = validation.data;

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

    // Verify all tasks belong to this project
    const taskIds = taskOrder.map((t) => t.id);
    const existingTasks = await db
      .select()
      .from(tasks)
      .where(inArray(tasks.id, taskIds));

    if (existingTasks.length !== taskIds.length) {
      return NextResponse.json(
        errorResponse('Invalid tasks', 'One or more task IDs do not exist'),
        { status: 400 }
      );
    }

    const invalidTasks = existingTasks.filter(
      (task) => task.projectId !== projectId
    );
    if (invalidTasks.length > 0) {
      return NextResponse.json(
        errorResponse(
          'Invalid tasks',
          `Tasks ${invalidTasks.map((t) => t.id).join(', ')} do not belong to project ${projectId}`
        ),
        { status: 400 }
      );
    }

    // Update each task's order and status (if provided)
    const updatePromises = taskOrder.map(async (taskUpdate) => {
      const updateData: { order: number; status?: string } = {
        order: taskUpdate.order,
      };

      if (taskUpdate.status) {
        updateData.status = taskUpdate.status;
      }

      return db
        .update(tasks)
        .set(updateData)
        .where(eq(tasks.id, taskUpdate.id))
        .returning();
    });

    const updatedTasks = await Promise.all(updatePromises);

    // Log reorder event
    await db.insert(activityLog).values({
      projectId,
      eventType: 'task_updated',
      eventData: {
        action: 'reorder',
        taskCount: taskOrder.length,
        taskIds: taskIds,
        newOrder: taskOrder,
      },
      agentReasoning: `User reordered ${taskOrder.length} task(s) via kanban board`,
    });

    return NextResponse.json(
      successResponse(
        updatedTasks.flat(),
        `Successfully reordered ${taskOrder.length} task(s)`
      )
    );
  } catch (error) {
    console.error('Error reordering tasks:', error);
    return NextResponse.json(
      errorResponse(
        'Failed to reorder tasks',
        error instanceof Error ? error.message : undefined
      ),
      { status: 500 }
    );
  }
}
