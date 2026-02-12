import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, activityLog } from '@/db/schema';
import { eq, and, or, desc } from 'drizzle-orm';
import {
  SubmitResponseSchema,
  successResponse,
  errorResponse,
  type SubmitResponseResponse,
} from '@/lib/api-types';

/**
 * POST /api/projects/[projectId]/responses
 * Submit a human response (decision, approval, or error recovery)
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
    const validation = SubmitResponseSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        errorResponse('Invalid request body', validation.error.errors),
        { status: 400 }
      );
    }

    const { responseType, responseId, value, notes } = validation.data;

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

    // Find the corresponding event by responseId
    let eventTypeToFind: string;
    let idField: string;

    switch (responseType) {
      case 'decision':
        eventTypeToFind = 'decision_needed';
        idField = 'decision_id';
        break;
      case 'approval':
        eventTypeToFind = 'approval_needed';
        idField = 'approval_id';
        break;
      case 'error_recovery':
        eventTypeToFind = 'error';
        idField = 'error_id';
        break;
      default:
        return NextResponse.json(
          errorResponse('Invalid response type', `Unknown response type: ${responseType}`),
          { status: 400 }
        );
    }

    // Find the event
    const events = await db
      .select()
      .from(activityLog)
      .where(
        and(
          eq(activityLog.projectId, projectId),
          eq(activityLog.eventType, eventTypeToFind)
        )
      )
      .orderBy(desc(activityLog.timestamp));

    const targetEvent = events.find(
      (e) => e.eventData && e.eventData[idField] === responseId
    );

    if (!targetEvent) {
      return NextResponse.json(
        errorResponse(
          'Response target not found',
          `No ${responseType} found with ID ${responseId}`
        ),
        { status: 404 }
      );
    }

    // Check if already responded
    if (targetEvent.eventData.resolved) {
      return NextResponse.json(
        errorResponse('Already responded', `This ${responseType} has already been resolved`),
        { status: 400 }
      );
    }

    // Update the event with the response
    const updatedEventData = {
      ...targetEvent.eventData,
      resolved: true,
      response: value,
      responseNotes: notes,
      respondedAt: new Date().toISOString(),
    };

    await db
      .update(activityLog)
      .set({
        eventData: updatedEventData,
      })
      .where(eq(activityLog.id, targetEvent.id));

    // Log the response submission
    await db.insert(activityLog).values({
      projectId,
      eventType: 'activity',
      eventData: {
        activity_type: 'response_submitted',
        responseType,
        responseId,
        value,
      },
      agentReasoning: notes || `Response submitted for ${responseType} ${responseId}`,
    });

    const response: SubmitResponseResponse = {
      success: true,
      message: `${responseType} response submitted successfully`,
      updatedEventId: targetEvent.id,
    };

    return NextResponse.json(successResponse(response));
  } catch (error) {
    console.error('Error submitting response:', error);
    return NextResponse.json(
      errorResponse('Failed to submit response', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
