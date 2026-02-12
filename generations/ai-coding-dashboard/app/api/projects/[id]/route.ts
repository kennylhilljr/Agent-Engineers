import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, tasks, activityLog } from '@/db/schema';
import { eq } from 'drizzle-orm';
import {
  UpdateProjectSchema,
  successResponse,
  errorResponse,
  type ProjectResponse,
} from '@/lib/api-types';

/**
 * GET /api/projects/[id]
 * Get a specific project by ID with task statistics
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const projectId = parseInt(params.id, 10);
    if (isNaN(projectId)) {
      return NextResponse.json(
        errorResponse('Invalid project ID', 'Project ID must be a number'),
        { status: 400 }
      );
    }

    // Fetch the project
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

    // Fetch task statistics
    const projectTasks = await db
      .select()
      .from(tasks)
      .where(eq(tasks.projectId, projectId));

    const taskCount = projectTasks.length;
    const completedTasks = projectTasks.filter((t) => t.status === 'done').length;
    const inProgressTasks = projectTasks.filter((t) => t.status === 'in_progress').length;
    const todoTasks = projectTasks.filter((t) => t.status === 'todo').length;
    const blockedTasks = projectTasks.filter((t) => t.status === 'blocked').length;
    const progress = taskCount > 0 ? Math.round((completedTasks / taskCount) * 100) : 0;

    const response: ProjectResponse = {
      ...project,
      taskCount,
      completedTasks,
      inProgressTasks,
      todoTasks,
      blockedTasks,
      progress,
    };

    return NextResponse.json(successResponse(response));
  } catch (error) {
    console.error('Error fetching project:', error);
    return NextResponse.json(
      errorResponse('Failed to fetch project', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}

/**
 * PATCH /api/projects/[id]
 * Update a project
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const projectId = parseInt(params.id, 10);
    if (isNaN(projectId)) {
      return NextResponse.json(
        errorResponse('Invalid project ID', 'Project ID must be a number'),
        { status: 400 }
      );
    }

    const body = await request.json();

    // Validate request body
    const validation = UpdateProjectSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        errorResponse('Invalid request body', validation.error.errors),
        { status: 400 }
      );
    }

    // Check if project exists
    const [existingProject] = await db
      .select()
      .from(projects)
      .where(eq(projects.id, projectId));

    if (!existingProject) {
      return NextResponse.json(
        errorResponse('Project not found', `No project found with ID ${projectId}`),
        { status: 404 }
      );
    }

    // Update the project
    const [updatedProject] = await db
      .update(projects)
      .set(validation.data)
      .where(eq(projects.id, projectId))
      .returning();

    // Log the update event
    await db.insert(activityLog).values({
      projectId,
      eventType: 'project_updated',
      eventData: {
        changes: validation.data,
        previousValues: {
          name: existingProject.name,
          spec: existingProject.spec,
          preferredLayout: existingProject.preferredLayout,
        },
      },
      agentReasoning: 'Project updated via API',
    });

    // Fetch task statistics
    const projectTasks = await db
      .select()
      .from(tasks)
      .where(eq(tasks.projectId, projectId));

    const taskCount = projectTasks.length;
    const completedTasks = projectTasks.filter((t) => t.status === 'done').length;
    const inProgressTasks = projectTasks.filter((t) => t.status === 'in_progress').length;
    const todoTasks = projectTasks.filter((t) => t.status === 'todo').length;
    const blockedTasks = projectTasks.filter((t) => t.status === 'blocked').length;
    const progress = taskCount > 0 ? Math.round((completedTasks / taskCount) * 100) : 0;

    const response: ProjectResponse = {
      ...updatedProject,
      taskCount,
      completedTasks,
      inProgressTasks,
      todoTasks,
      blockedTasks,
      progress,
    };

    return NextResponse.json(successResponse(response, 'Project updated successfully'));
  } catch (error) {
    console.error('Error updating project:', error);
    return NextResponse.json(
      errorResponse('Failed to update project', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/projects/[id]
 * Delete a project (cascades to tasks and activity log)
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const projectId = parseInt(params.id, 10);
    if (isNaN(projectId)) {
      return NextResponse.json(
        errorResponse('Invalid project ID', 'Project ID must be a number'),
        { status: 400 }
      );
    }

    // Check if project exists
    const [existingProject] = await db
      .select()
      .from(projects)
      .where(eq(projects.id, projectId));

    if (!existingProject) {
      return NextResponse.json(
        errorResponse('Project not found', `No project found with ID ${projectId}`),
        { status: 404 }
      );
    }

    // Delete the project (cascades to tasks and activity log due to onDelete: 'cascade')
    await db.delete(projects).where(eq(projects.id, projectId));

    return NextResponse.json(
      successResponse({ id: projectId }, `Project "${existingProject.name}" deleted successfully`)
    );
  } catch (error) {
    console.error('Error deleting project:', error);
    return NextResponse.json(
      errorResponse('Failed to delete project', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
