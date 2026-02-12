import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, tasks, activityLog } from '@/db/schema';
import { eq, asc } from 'drizzle-orm';
import {
  CreateTaskSchema,
  successResponse,
  errorResponse,
  type TaskResponse,
} from '@/lib/api-types';

/**
 * GET /api/projects/[projectId]/tasks
 * List all tasks for a project
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

    // Fetch all tasks for the project, ordered by order field
    const projectTasks = await db
      .select()
      .from(tasks)
      .where(eq(tasks.projectId, projectId))
      .orderBy(asc(tasks.order));

    const response: TaskResponse[] = projectTasks;

    return NextResponse.json(
      successResponse(response, `Found ${projectTasks.length} tasks`)
    );
  } catch (error) {
    console.error('Error fetching tasks:', error);
    return NextResponse.json(
      errorResponse('Failed to fetch tasks', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}

/**
 * POST /api/projects/[projectId]/tasks
 * Create a new task for a project
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
    const validation = CreateTaskSchema.safeParse({
      ...body,
      projectId, // Ensure projectId matches the URL parameter
    });
    if (!validation.success) {
      return NextResponse.json(
        errorResponse('Invalid request body', validation.error.errors),
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

    // Create the task
    const [newTask] = await db
      .insert(tasks)
      .values(validation.data)
      .returning();

    // Log task creation event
    await db.insert(activityLog).values({
      projectId,
      eventType: 'task_created',
      eventData: {
        taskId: newTask.id,
        category: newTask.category,
        description: newTask.description,
        status: newTask.status,
      },
      agentReasoning: `Task created: ${newTask.description}`,
    });

    const response: TaskResponse = newTask;

    return NextResponse.json(
      successResponse(response, 'Task created successfully'),
      { status: 201 }
    );
  } catch (error) {
    console.error('Error creating task:', error);
    return NextResponse.json(
      errorResponse('Failed to create task', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
