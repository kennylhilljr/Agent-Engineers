import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { projects, activityLog } from '@/db/schema';
import { eq, desc, and, gte, lte } from 'drizzle-orm';
import {
  QueryEventsSchema,
  CreateEventSchema,
  successResponse,
  errorResponse,
  paginatedResponse,
  type EventResponse,
} from '@/lib/api-types';

/**
 * GET /api/projects/[projectId]/events
 * Get event history for a project with filtering
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

    // Parse query parameters
    const searchParams = request.nextUrl.searchParams;
    const queryParams = {
      eventType: searchParams.get('eventType') || undefined,
      limit: searchParams.get('limit') ? parseInt(searchParams.get('limit')!, 10) : 100,
      offset: searchParams.get('offset') ? parseInt(searchParams.get('offset')!, 10) : 0,
      startDate: searchParams.get('startDate') || undefined,
      endDate: searchParams.get('endDate') || undefined,
    };

    // Validate query parameters
    const validation = QueryEventsSchema.safeParse(queryParams);
    if (!validation.success) {
      return NextResponse.json(
        errorResponse('Invalid query parameters', validation.error.errors),
        { status: 400 }
      );
    }

    const { eventType, limit, offset, startDate, endDate } = validation.data;

    // Build query conditions
    const conditions = [eq(activityLog.projectId, projectId)];

    if (eventType) {
      conditions.push(eq(activityLog.eventType, eventType));
    }

    if (startDate) {
      conditions.push(gte(activityLog.timestamp, new Date(startDate)));
    }

    if (endDate) {
      conditions.push(lte(activityLog.timestamp, new Date(endDate)));
    }

    // Fetch events with pagination
    const events = await db
      .select()
      .from(activityLog)
      .where(and(...conditions))
      .orderBy(desc(activityLog.timestamp))
      .limit(limit)
      .offset(offset);

    // Get total count for pagination
    const allEvents = await db
      .select()
      .from(activityLog)
      .where(and(...conditions));

    const response: EventResponse[] = events;

    return NextResponse.json(
      paginatedResponse(response, allEvents.length, limit, offset)
    );
  } catch (error) {
    console.error('Error fetching events:', error);
    return NextResponse.json(
      errorResponse('Failed to fetch events', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}

/**
 * POST /api/projects/[projectId]/events
 * Create a new event for a project
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
    const validation = CreateEventSchema.safeParse({
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

    // Create the event
    const [newEvent] = await db
      .insert(activityLog)
      .values(validation.data)
      .returning();

    const response: EventResponse = newEvent;

    return NextResponse.json(
      successResponse(response, 'Event created successfully'),
      { status: 201 }
    );
  } catch (error) {
    console.error('Error creating event:', error);
    return NextResponse.json(
      errorResponse('Failed to create event', error instanceof Error ? error.message : undefined),
      { status: 500 }
    );
  }
}
