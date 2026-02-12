import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, activityLog } from '@/db/schema';
import { eq } from 'drizzle-orm';
import {
  successResponse,
  errorResponse,
  type ExecutionResponse,
} from '@/lib/api-types';

/**
 * POST /api/projects/[projectId]/pause
 * Pause agent execution for a project
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

    // Log execution pause event
    await db.insert(activityLog).values({
      projectId,
      eventType: 'execution_paused',
      eventData: {
        pausedAt: new Date().toISOString(),
      },
      agentReasoning: `Execution paused for project "${project.name}"`,
    });

    const response: ExecutionResponse = {
      status: 'paused',
      pausedAt: new Date().toISOString(),
      message: `Execution paused for project "${project.name}"`,
    };

    return NextResponse.json(
      successResponse(response, 'Execution paused successfully')
    );
  } catch (error) {
    console.error('Error pausing execution:', error);
    return NextResponse.json(
      errorResponse('Failed to pause execution', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
