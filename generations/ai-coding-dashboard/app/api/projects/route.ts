import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, tasks, activityLog } from '@/db/schema';
import { eq, desc } from 'drizzle-orm';
import {
  CreateProjectSchema,
  successResponse,
  errorResponse,
  type ProjectResponse,
} from '@/lib/api-types';

/**
 * GET /api/projects
 * List all projects with task counts and progress
 */
export async function GET(request: NextRequest) {
  try {
    // Fetch all projects ordered by creation date (newest first)
    const allProjects = await db
      .select()
      .from(projects)
      .orderBy(desc(projects.createdAt));

    // Enhance each project with task counts and progress
    const enhancedProjects: ProjectResponse[] = await Promise.all(
      allProjects.map(async (project) => {
        const projectTasks = await db
          .select()
          .from(tasks)
          .where(eq(tasks.projectId, project.id));

        const taskCount = projectTasks.length;
        const completedTasks = projectTasks.filter((t) => t.status === 'done').length;
        const inProgressTasks = projectTasks.filter((t) => t.status === 'in_progress').length;
        const todoTasks = projectTasks.filter((t) => t.status === 'todo').length;
        const blockedTasks = projectTasks.filter((t) => t.status === 'blocked').length;
        const progress = taskCount > 0 ? Math.round((completedTasks / taskCount) * 100) : 0;

        return {
          ...project,
          taskCount,
          completedTasks,
          inProgressTasks,
          todoTasks,
          blockedTasks,
          progress,
        };
      })
    );

    return NextResponse.json(
      successResponse(enhancedProjects, `Found ${enhancedProjects.length} projects`)
    );
  } catch (error) {
    console.error('Error fetching projects:', error);
    return NextResponse.json(
      errorResponse('Failed to fetch projects', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}

/**
 * POST /api/projects
 * Create a new project from spec
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate request body
    const validation = CreateProjectSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        errorResponse('Invalid request body', validation.error.errors),
        { status: 400 }
      );
    }

    const { name, spec, preferredLayout, userId, specData } = validation.data;

    // Create the project
    const [newProject] = await db
      .insert(projects)
      .values({
        name,
        spec,
        preferredLayout: preferredLayout || 'kanban',
        userId,
      })
      .returning();

    // Log project creation event
    await db.insert(activityLog).values({
      projectId: newProject.id,
      eventType: 'project_created',
      eventData: {
        projectName: name,
        preferredLayout: preferredLayout || 'kanban',
        specData,
      },
      agentReasoning: `Project "${name}" created by user ${userId}`,
    });

    // Parse spec data if provided to create initial tasks
    if (specData && specData.tasks && Array.isArray(specData.tasks)) {
      const tasksToCreate = specData.tasks.map((task: any, index: number) => ({
        projectId: newProject.id,
        category: task.category || 'general',
        description: task.description || '',
        steps: task.steps || [],
        status: 'todo' as const,
        order: index,
      }));

      if (tasksToCreate.length > 0) {
        await db.insert(tasks).values(tasksToCreate);
      }
    }

    // Fetch task count for response
    const projectTasks = await db
      .select()
      .from(tasks)
      .where(eq(tasks.projectId, newProject.id));

    const response: ProjectResponse = {
      ...newProject,
      taskCount: projectTasks.length,
      completedTasks: 0,
      inProgressTasks: 0,
      todoTasks: projectTasks.length,
      blockedTasks: 0,
      progress: 0,
    };

    return NextResponse.json(
      successResponse(response, `Project "${name}" created successfully`),
      { status: 201 }
    );
  } catch (error) {
    console.error('Error creating project:', error);
    return NextResponse.json(
      errorResponse('Failed to create project', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
