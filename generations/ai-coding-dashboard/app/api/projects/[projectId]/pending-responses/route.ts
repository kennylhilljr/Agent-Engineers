import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, activityLog } from '@/db/schema';
import { eq, and, or, desc } from 'drizzle-orm';
import {
  successResponse,
  errorResponse,
  type PendingResponseItem,
} from '@/lib/api-types';

/**
 * GET /api/projects/[projectId]/pending-responses
 * Get all pending responses (decisions, approvals, errors) for a project
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

    // Fetch all pending events (decisions, approvals, errors)
    const events = await db
      .select()
      .from(activityLog)
      .where(
        and(
          eq(activityLog.projectId, projectId),
          or(
            eq(activityLog.eventType, 'decision_needed'),
            eq(activityLog.eventType, 'approval_needed'),
            eq(activityLog.eventType, 'error')
          )
        )
      )
      .orderBy(desc(activityLog.timestamp));

    // Filter out resolved events and transform to PendingResponseItem
    const pendingResponses: PendingResponseItem[] = events
      .filter((event) => !event.eventData.resolved)
      .map((event) => {
        let responseType: 'decision' | 'approval' | 'error_recovery';
        let id: string;
        let question: string | undefined;
        let action: string | undefined;
        let errorMessage: string | undefined;
        let options: string[] | undefined;
        let priority: 'low' | 'medium' | 'high' | undefined;
        let riskLevel: 'low' | 'medium' | 'high' | undefined;

        if (event.eventType === 'decision_needed') {
          responseType = 'decision';
          id = event.eventData.decision_id;
          question = event.eventData.question;
          options = event.eventData.options;
          priority = event.eventData.priority;
        } else if (event.eventType === 'approval_needed') {
          responseType = 'approval';
          id = event.eventData.approval_id;
          action = event.eventData.action;
          riskLevel = event.eventData.risk_level;
        } else {
          // error
          responseType = 'error_recovery';
          id = event.eventData.error_id;
          errorMessage = event.eventData.error_message;
        }

        return {
          id,
          responseType,
          question,
          action,
          errorMessage,
          options,
          priority,
          riskLevel,
          timestamp: event.timestamp.toISOString(),
          eventData: event.eventData,
        };
      });

    return NextResponse.json(
      successResponse(
        {
          pendingResponses,
          count: pendingResponses.length,
        },
        `Found ${pendingResponses.length} pending responses`
      )
    );
  } catch (error) {
    console.error('Error fetching pending responses:', error);
    return NextResponse.json(
      errorResponse(
        'Failed to fetch pending responses',
        error instanceof Error ? error.message : undefined
      ),
      { status: 500 }
    );
  }
}
