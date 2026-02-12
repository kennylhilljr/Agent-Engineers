/**
 * KAN-83: End-to-end tests for external agent integration
 *
 * Simulates Claude Code sending events via the dashboard API and verifies
 * the complete event ingestion, response submission, and polling flow.
 *
 * Tests the following endpoints:
 *   POST /api/dashboard/event
 *   POST /api/dashboard/response
 *   GET  /api/dashboard/pending-responses
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { NextRequest } from 'next/server';

// ---------------------------------------------------------------------------
// Mock database layer
// ---------------------------------------------------------------------------

/** In-memory store that simulates the activity_log table */
let dbRows: Array<{
  id: number;
  projectId: number;
  eventType: string;
  eventData: Record<string, any>;
  agentReasoning: string | null;
  timestamp: Date;
}> = [];

let nextId = 1;

/**
 * Build a chainable query builder that mimics the Drizzle ORM API surface
 * used by the three route handlers under test.
 */
function createMockDb() {
  return {
    insert: vi.fn().mockImplementation((table: any) => ({
      values: vi.fn().mockImplementation((values: any) => ({
        returning: vi.fn().mockImplementation(() => {
          const row = {
            id: nextId++,
            projectId: values.projectId,
            eventType: values.eventType,
            eventData: values.eventData,
            agentReasoning: values.agentReasoning ?? null,
            timestamp: new Date(),
          };
          dbRows.push(row);
          return [row];
        }),
      })),
    })),
    select: vi.fn().mockImplementation(() => ({
      from: vi.fn().mockImplementation((table: any) => ({
        where: vi.fn().mockImplementation((condition: any) => {
          // Return all rows -- the route handlers do their own filtering
          return Promise.resolve(dbRows);
        }),
      })),
    })),
  };
}

vi.mock('@/lib/db', () => ({
  getDb: vi.fn(() => createMockDb()),
  db: {},
}));

vi.mock('@/db/schema', () => ({
  activityLog: { projectId: 'project_id' },
}));

vi.mock('drizzle-orm', () => ({
  eq: vi.fn((col: any, val: any) => ({ col, val })),
  and: vi.fn((...args: any[]) => args),
}));

// ---------------------------------------------------------------------------
// Import route handlers (after mocks are in place)
// ---------------------------------------------------------------------------

import { POST as eventPOST } from '@/app/api/dashboard/event/route';
import { POST as responsePOST } from '@/app/api/dashboard/response/route';
import { GET as pendingGET } from '@/app/api/dashboard/pending-responses/route';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PROJECT_ID = 42;

/** Create a NextRequest for a JSON POST */
function postRequest(url: string, body: Record<string, any>): NextRequest {
  return new NextRequest(new URL(url, 'http://localhost:3000'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/** Create a NextRequest for a GET with query params */
function getRequest(url: string): NextRequest {
  return new NextRequest(new URL(url, 'http://localhost:3000'), {
    method: 'GET',
  });
}

/** Extract JSON body from a NextResponse */
async function jsonOf(response: Response): Promise<any> {
  return response.json();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('KAN-83: External Agent Integration E2E', () => {
  beforeEach(() => {
    dbRows = [];
    nextId = 1;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // -----------------------------------------------------------------------
  // 1. task_started events
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/event - task_started', () => {
    it('accepts a valid task_started event', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'task_started',
        payload: {
          task_id: 1,
          task_name: 'Implement login page',
          estimated_duration: '2 hours',
        },
        agent_reasoning: 'Starting first task from the project plan',
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(201);
      expect(data.success).toBe(true);
      expect(data.event_id).toBeDefined();
      expect(data.message).toContain('task_started');
    });
  });

  // -----------------------------------------------------------------------
  // 2. decision_needed events
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/event - decision_needed', () => {
    it('accepts a valid decision_needed event', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'decision_needed',
        payload: {
          decision_id: 'dec-001',
          question: 'Which CSS framework should we use?',
          options: ['Tailwind CSS', 'CSS Modules', 'styled-components'],
          priority: 'high',
        },
        agent_reasoning: 'Need human input on styling approach',
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(201);
      expect(data.success).toBe(true);
      expect(data.message).toContain('decision_needed');
    });
  });

  // -----------------------------------------------------------------------
  // 3. approval_needed events
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/event - approval_needed', () => {
    it('accepts a valid approval_needed event', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'approval_needed',
        payload: {
          approval_id: 'apr-001',
          action: 'Delete legacy database migration files',
          description: 'Removing 12 legacy migration files that are no longer needed',
          risk_level: 'medium',
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(201);
      expect(data.success).toBe(true);
      expect(data.message).toContain('approval_needed');
    });
  });

  // -----------------------------------------------------------------------
  // 4. milestone events
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/event - milestone', () => {
    it('accepts a valid milestone event', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'milestone',
        payload: {
          milestone_name: 'Authentication Module Complete',
          description: 'All auth routes, middleware, and session management implemented',
          completion_percentage: 40,
        },
        agent_reasoning: 'Completed auth module ahead of schedule',
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(201);
      expect(data.success).toBe(true);
      expect(data.message).toContain('milestone');
    });
  });

  // -----------------------------------------------------------------------
  // 5. error events
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/event - error', () => {
    it('accepts a valid error event', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'error',
        payload: {
          error_id: 'err-001',
          error_message: 'TypeScript compilation failed: Cannot find module @/lib/auth',
          error_type: 'compilation',
          recoverable: true,
          suggested_action: 'Install missing dependency or check import path',
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(201);
      expect(data.success).toBe(true);
      expect(data.message).toContain('error');
    });
  });

  // -----------------------------------------------------------------------
  // 6. file_changed events
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/event - file_changed', () => {
    it('accepts a valid file_changed event', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'file_changed',
        payload: {
          file_path: 'src/components/LoginForm.tsx',
          change_type: 'created',
          lines_added: 85,
          lines_removed: 0,
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(201);
      expect(data.success).toBe(true);
      expect(data.message).toContain('file_changed');
    });

    it('accepts file_changed with change_type modified', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'file_changed',
        payload: {
          file_path: 'src/lib/db.ts',
          change_type: 'modified',
          lines_added: 12,
          lines_removed: 5,
        },
      });

      const res = await eventPOST(req);
      expect(res.status).toBe(201);
    });

    it('accepts file_changed with change_type deleted', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'file_changed',
        payload: {
          file_path: 'src/old-module.ts',
          change_type: 'deleted',
        },
      });

      const res = await eventPOST(req);
      expect(res.status).toBe(201);
    });
  });

  // -----------------------------------------------------------------------
  // 7. Payload schema validation
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/event - payload validation', () => {
    it('rejects task_started without task_id', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'task_started',
        payload: {
          task_name: 'Missing task_id',
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('task_id');
    });

    it('rejects task_started without task_name', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'task_started',
        payload: {
          task_id: 1,
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('task_name');
    });

    it('rejects decision_needed without decision_id', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'decision_needed',
        payload: {
          question: 'What framework?',
          options: ['React', 'Vue'],
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('decision_id');
    });

    it('rejects decision_needed with empty options', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'decision_needed',
        payload: {
          decision_id: 'dec-fail',
          question: 'What framework?',
          options: [],
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('options');
    });

    it('rejects approval_needed without description', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'approval_needed',
        payload: {
          approval_id: 'apr-fail',
          action: 'Delete files',
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('description');
    });

    it('rejects error without recoverable flag', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'error',
        payload: {
          error_id: 'err-fail',
          error_message: 'Something broke',
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('recoverable');
    });

    it('rejects milestone without description', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'milestone',
        payload: {
          milestone_name: 'Phase 1',
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('description');
    });

    it('rejects file_changed with invalid change_type', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'file_changed',
        payload: {
          file_path: 'src/foo.ts',
          change_type: 'renamed', // not valid
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('change_type');
    });

    it('rejects event with missing project_id', async () => {
      const req = postRequest('/api/dashboard/event', {
        type: 'task_started',
        payload: { task_id: 1, task_name: 'Foo' },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('project_id');
    });

    it('rejects event with non-object payload', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'task_started',
        payload: 'not_an_object',
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('Payload must be an object');
    });
  });

  // -----------------------------------------------------------------------
  // 8. Invalid event types
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/event - invalid event types', () => {
    it('rejects an unknown event type', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'unknown_type',
        payload: { foo: 'bar' },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('Invalid event type');
    });

    it('rejects missing event type', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        payload: { foo: 'bar' },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('Invalid event type');
    });
  });

  // -----------------------------------------------------------------------
  // 9. Decision responses
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/response - decision response', () => {
    it('accepts a valid decision response', async () => {
      // Seed the in-memory DB with a decision_needed event
      dbRows.push({
        id: nextId++,
        projectId: PROJECT_ID,
        eventType: 'decision_needed',
        eventData: {
          decision_id: 'dec-100',
          question: 'Which ORM?',
          options: ['Drizzle', 'Prisma'],
        },
        agentReasoning: null,
        timestamp: new Date(),
      });

      const req = postRequest('/api/dashboard/response', {
        project_id: PROJECT_ID,
        response_type: 'decision',
        response_id: 'dec-100',
        value: 'Drizzle',
        notes: 'Drizzle has better type safety',
      });

      const res = await responsePOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.message).toContain('decision');
      expect(data.message).toContain('dec-100');
    });

    it('rejects decision response with missing value', async () => {
      const req = postRequest('/api/dashboard/response', {
        project_id: PROJECT_ID,
        response_type: 'decision',
        response_id: 'dec-100',
      });

      const res = await responsePOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('value');
    });
  });

  // -----------------------------------------------------------------------
  // 10. Approval responses
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/response - approval response', () => {
    it('accepts a valid approval response', async () => {
      dbRows.push({
        id: nextId++,
        projectId: PROJECT_ID,
        eventType: 'approval_needed',
        eventData: {
          approval_id: 'apr-200',
          action: 'Deploy to production',
          description: 'Deploying v2.0 to production',
          risk_level: 'high',
        },
        agentReasoning: null,
        timestamp: new Date(),
      });

      const req = postRequest('/api/dashboard/response', {
        project_id: PROJECT_ID,
        response_type: 'approval',
        response_id: 'apr-200',
        value: true,
        notes: 'Approved after reviewing diff',
      });

      const res = await responsePOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.message).toContain('approval');
      expect(data.message).toContain('apr-200');
    });

    it('rejects approval response for non-existent approval', async () => {
      const req = postRequest('/api/dashboard/response', {
        project_id: PROJECT_ID,
        response_type: 'approval',
        response_id: 'apr-nonexistent',
        value: false,
      });

      const res = await responsePOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(404);
      expect(data.success).toBe(false);
      expect(data.error).toContain('No pending approval');
    });

    it('rejects approval response with invalid response_type', async () => {
      const req = postRequest('/api/dashboard/response', {
        project_id: PROJECT_ID,
        response_type: 'unknown_type',
        response_id: 'apr-200',
        value: true,
      });

      const res = await responsePOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('Invalid response_type');
    });
  });

  // -----------------------------------------------------------------------
  // 11. Error recovery responses
  // -----------------------------------------------------------------------
  describe('POST /api/dashboard/response - error_recovery response', () => {
    it('accepts a valid error recovery response', async () => {
      dbRows.push({
        id: nextId++,
        projectId: PROJECT_ID,
        eventType: 'error',
        eventData: {
          error_id: 'err-300',
          error_message: 'Build failed: missing dependency',
          recoverable: true,
          suggested_action: 'Run npm install',
        },
        agentReasoning: null,
        timestamp: new Date(),
      });

      const req = postRequest('/api/dashboard/response', {
        project_id: PROJECT_ID,
        response_type: 'error_recovery',
        response_id: 'err-300',
        value: 'retry_with_install',
        notes: 'Agent should run npm install and retry',
      });

      const res = await responsePOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.message).toContain('error_recovery');
      expect(data.message).toContain('err-300');
    });

    it('rejects error_recovery response without response_id', async () => {
      const req = postRequest('/api/dashboard/response', {
        project_id: PROJECT_ID,
        response_type: 'error_recovery',
        value: 'retry',
      });

      const res = await responsePOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('response_id');
    });
  });

  // -----------------------------------------------------------------------
  // 12. GET /api/dashboard/pending-responses
  // -----------------------------------------------------------------------
  describe('GET /api/dashboard/pending-responses', () => {
    it('returns unacknowledged pending responses', async () => {
      // Seed decision_needed and approval_needed events
      dbRows.push(
        {
          id: nextId++,
          projectId: PROJECT_ID,
          eventType: 'decision_needed',
          eventData: {
            decision_id: 'dec-pend-1',
            question: 'Use REST or GraphQL?',
            options: ['REST', 'GraphQL'],
            priority: 'medium',
          },
          agentReasoning: null,
          timestamp: new Date(),
        },
        {
          id: nextId++,
          projectId: PROJECT_ID,
          eventType: 'approval_needed',
          eventData: {
            approval_id: 'apr-pend-1',
            action: 'Refactor auth module',
            description: 'Major refactor of authentication system',
            risk_level: 'high',
          },
          agentReasoning: null,
          timestamp: new Date(),
        },
      );

      const req = getRequest(
        `/api/dashboard/pending-responses?project_id=${PROJECT_ID}`,
      );

      const res = await pendingGET(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.pending_responses).toBeDefined();
      expect(Array.isArray(data.pending_responses)).toBe(true);
      expect(data.count).toBe(2);

      // Verify the decision pending response shape
      const decision = data.pending_responses.find(
        (r: any) => r.id === 'dec-pend-1',
      );
      expect(decision).toBeDefined();
      expect(decision.response_type).toBe('decision');
      expect(decision.question).toBe('Use REST or GraphQL?');
      expect(decision.options).toEqual(['REST', 'GraphQL']);

      // Verify the approval pending response shape
      const approval = data.pending_responses.find(
        (r: any) => r.id === 'apr-pend-1',
      );
      expect(approval).toBeDefined();
      expect(approval.response_type).toBe('approval');
      expect(approval.action).toBe('Refactor auth module');
    });

    it('returns empty list when no pending items exist', async () => {
      const req = getRequest(
        `/api/dashboard/pending-responses?project_id=${PROJECT_ID}`,
      );

      const res = await pendingGET(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.pending_responses).toEqual([]);
      expect(data.count).toBe(0);
    });

    it('rejects request without project_id', async () => {
      const req = getRequest('/api/dashboard/pending-responses');

      const res = await pendingGET(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('project_id');
    });

    it('rejects request with non-numeric project_id', async () => {
      const req = getRequest(
        '/api/dashboard/pending-responses?project_id=abc',
      );

      const res = await pendingGET(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('valid number');
    });
  });

  // -----------------------------------------------------------------------
  // 13. Acknowledge responses (pending items disappear after response)
  // -----------------------------------------------------------------------
  describe('Acknowledge responses - resolved items excluded from pending', () => {
    it('does not return items that already have a response', async () => {
      // Seed a decision_needed event
      dbRows.push({
        id: nextId++,
        projectId: PROJECT_ID,
        eventType: 'decision_needed',
        eventData: {
          decision_id: 'dec-ack-1',
          question: 'Choose DB?',
          options: ['Postgres', 'MySQL'],
        },
        agentReasoning: null,
        timestamp: new Date(),
      });

      // Also seed the corresponding decision_response (simulating acknowledgment)
      dbRows.push({
        id: nextId++,
        projectId: PROJECT_ID,
        eventType: 'decision_response',
        eventData: {
          original_event_id: dbRows[dbRows.length - 1].id,
          response_id: 'dec-ack-1',
          response_type: 'decision',
          value: 'Postgres',
          notes: null,
          timestamp: new Date().toISOString(),
        },
        agentReasoning: null,
        timestamp: new Date(),
      });

      const req = getRequest(
        `/api/dashboard/pending-responses?project_id=${PROJECT_ID}`,
      );

      const res = await pendingGET(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(200);
      expect(data.success).toBe(true);
      // The decision that was already responded to should be excluded
      const found = data.pending_responses.find(
        (r: any) => r.id === 'dec-ack-1',
      );
      expect(found).toBeUndefined();
      expect(data.count).toBe(0);
    });
  });

  // -----------------------------------------------------------------------
  // 14. Full event -> response -> poll flow end-to-end
  // -----------------------------------------------------------------------
  describe('Full event -> response -> poll flow', () => {
    it('complete lifecycle: send event, poll pending, submit response, verify cleared', async () => {
      // Step 1: Agent sends a decision_needed event
      const eventReq = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'decision_needed',
        payload: {
          decision_id: 'dec-e2e-flow',
          question: 'Which testing framework?',
          options: ['vitest', 'jest', 'mocha'],
          priority: 'high',
        },
        agent_reasoning: 'Multiple viable options, need human preference',
      });

      const eventRes = await eventPOST(eventReq);
      const eventData = await jsonOf(eventRes);

      expect(eventRes.status).toBe(201);
      expect(eventData.success).toBe(true);
      const eventId = eventData.event_id;
      expect(eventId).toBeDefined();

      // Step 2: Agent polls for pending responses and sees the decision
      const pollReq = getRequest(
        `/api/dashboard/pending-responses?project_id=${PROJECT_ID}`,
      );

      const pollRes = await pendingGET(pollReq);
      const pollData = await jsonOf(pollRes);

      expect(pollRes.status).toBe(200);
      expect(pollData.count).toBeGreaterThanOrEqual(1);
      const pending = pollData.pending_responses.find(
        (r: any) => r.id === 'dec-e2e-flow',
      );
      expect(pending).toBeDefined();
      expect(pending.response_type).toBe('decision');
      expect(pending.question).toBe('Which testing framework?');
      expect(pending.options).toEqual(['vitest', 'jest', 'mocha']);

      // Step 3: Human submits a decision response via the dashboard
      const responseReq = postRequest('/api/dashboard/response', {
        project_id: PROJECT_ID,
        response_type: 'decision',
        response_id: 'dec-e2e-flow',
        value: 'vitest',
        notes: 'Vitest is fastest for Vite projects',
      });

      const responseRes = await responsePOST(responseReq);
      const responseData = await jsonOf(responseRes);

      expect(responseRes.status).toBe(200);
      expect(responseData.success).toBe(true);

      // Step 4: Agent polls again -- the decision should no longer be pending
      const pollReq2 = getRequest(
        `/api/dashboard/pending-responses?project_id=${PROJECT_ID}`,
      );

      const pollRes2 = await pendingGET(pollReq2);
      const pollData2 = await jsonOf(pollRes2);

      expect(pollRes2.status).toBe(200);
      const stillPending = pollData2.pending_responses.find(
        (r: any) => r.id === 'dec-e2e-flow',
      );
      expect(stillPending).toBeUndefined();
    });

    it('complete lifecycle for error recovery flow', async () => {
      // Step 1: Agent sends an error event
      const eventReq = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'error',
        payload: {
          error_id: 'err-e2e-flow',
          error_message: 'Test suite failed: 3 tests failing in auth module',
          error_type: 'test_failure',
          recoverable: true,
          suggested_action: 'Skip failing tests or fix assertions',
        },
        agent_reasoning: 'Tests are failing, need guidance on how to proceed',
      });

      const eventRes = await eventPOST(eventReq);
      expect(eventRes.status).toBe(201);

      // Step 2: Poll for pending -- error should appear
      const pollRes = await pendingGET(
        getRequest(`/api/dashboard/pending-responses?project_id=${PROJECT_ID}`),
      );
      const pollData = await jsonOf(pollRes);

      const pendingError = pollData.pending_responses.find(
        (r: any) => r.id === 'err-e2e-flow',
      );
      expect(pendingError).toBeDefined();
      expect(pendingError.response_type).toBe('error_recovery');
      expect(pendingError.error_message).toBe(
        'Test suite failed: 3 tests failing in auth module',
      );

      // Step 3: Human submits recovery action
      const responseRes = await responsePOST(
        postRequest('/api/dashboard/response', {
          project_id: PROJECT_ID,
          response_type: 'error_recovery',
          response_id: 'err-e2e-flow',
          value: 'fix_assertions',
          notes: 'Fix the test assertions to match new API response shape',
        }),
      );
      expect(responseRes.status).toBe(200);

      // Step 4: Error should no longer be pending
      const pollRes2 = await pendingGET(
        getRequest(`/api/dashboard/pending-responses?project_id=${PROJECT_ID}`),
      );
      const pollData2 = await jsonOf(pollRes2);

      const cleared = pollData2.pending_responses.find(
        (r: any) => r.id === 'err-e2e-flow',
      );
      expect(cleared).toBeUndefined();
    });
  });

  // -----------------------------------------------------------------------
  // 15. Rapid sequential events
  // -----------------------------------------------------------------------
  describe('Rapid sequential events', () => {
    it('handles multiple events sent in quick succession', async () => {
      const events = [
        {
          project_id: PROJECT_ID,
          type: 'task_started',
          payload: { task_id: 10, task_name: 'Setup project' },
        },
        {
          project_id: PROJECT_ID,
          type: 'file_changed',
          payload: { file_path: 'package.json', change_type: 'modified' },
        },
        {
          project_id: PROJECT_ID,
          type: 'file_changed',
          payload: { file_path: 'tsconfig.json', change_type: 'created' },
        },
        {
          project_id: PROJECT_ID,
          type: 'milestone',
          payload: {
            milestone_name: 'Project scaffolding complete',
            description: 'All config files created',
          },
        },
        {
          project_id: PROJECT_ID,
          type: 'activity',
          payload: {
            activity_type: 'command_run',
            message: 'Ran npm install',
          },
        },
        {
          project_id: PROJECT_ID,
          type: 'file_changed',
          payload: {
            file_path: 'src/index.ts',
            change_type: 'created',
            lines_added: 25,
          },
        },
        {
          project_id: PROJECT_ID,
          type: 'decision_needed',
          payload: {
            decision_id: 'dec-rapid-1',
            question: 'Use ESLint or Biome?',
            options: ['ESLint', 'Biome'],
          },
        },
        {
          project_id: PROJECT_ID,
          type: 'approval_needed',
          payload: {
            approval_id: 'apr-rapid-1',
            action: 'Add husky pre-commit hooks',
            description: 'Adding pre-commit hooks for linting',
          },
        },
        {
          project_id: PROJECT_ID,
          type: 'error',
          payload: {
            error_id: 'err-rapid-1',
            error_message: 'Lint warning in index.ts',
            recoverable: true,
          },
        },
        {
          project_id: PROJECT_ID,
          type: 'file_changed',
          payload: {
            file_path: '.eslintrc.json',
            change_type: 'created',
          },
        },
      ];

      // Fire all events concurrently (simulates rapid submission)
      const results = await Promise.all(
        events.map((ev) =>
          eventPOST(postRequest('/api/dashboard/event', ev)),
        ),
      );

      // Every event should have been accepted
      for (let i = 0; i < results.length; i++) {
        const data = await jsonOf(results[i]);
        expect(results[i].status).toBe(201);
        expect(data.success).toBe(true);
        expect(data.event_id).toBeDefined();
      }

      // All event IDs should be unique
      const eventIds = await Promise.all(
        results.map(async (r) => (await r.clone().json()).event_id),
      );
      const uniqueIds = new Set(eventIds);
      expect(uniqueIds.size).toBe(events.length);
    });

    it('correctly tracks pending items from rapid events', async () => {
      // Clear and seed fresh data
      dbRows = [];
      nextId = 1;

      // Fire decision + approval + error events
      const pendingEvents = [
        {
          project_id: PROJECT_ID,
          type: 'decision_needed',
          payload: {
            decision_id: 'dec-batch-1',
            question: 'Q1?',
            options: ['A', 'B'],
          },
        },
        {
          project_id: PROJECT_ID,
          type: 'decision_needed',
          payload: {
            decision_id: 'dec-batch-2',
            question: 'Q2?',
            options: ['C', 'D'],
          },
        },
        {
          project_id: PROJECT_ID,
          type: 'approval_needed',
          payload: {
            approval_id: 'apr-batch-1',
            action: 'Action 1',
            description: 'Desc 1',
          },
        },
        {
          project_id: PROJECT_ID,
          type: 'error',
          payload: {
            error_id: 'err-batch-1',
            error_message: 'Error 1',
            recoverable: true,
          },
        },
      ];

      await Promise.all(
        pendingEvents.map((ev) =>
          eventPOST(postRequest('/api/dashboard/event', ev)),
        ),
      );

      // Poll pending -- should see all 4
      const pollRes = await pendingGET(
        getRequest(`/api/dashboard/pending-responses?project_id=${PROJECT_ID}`),
      );
      const pollData = await jsonOf(pollRes);

      expect(pollRes.status).toBe(200);
      expect(pollData.count).toBe(4);

      // Verify each type is represented
      const types = pollData.pending_responses.map(
        (r: any) => r.response_type,
      );
      expect(types).toContain('decision');
      expect(types).toContain('approval');
      expect(types).toContain('error_recovery');

      // Respond to one decision and verify count drops
      await responsePOST(
        postRequest('/api/dashboard/response', {
          project_id: PROJECT_ID,
          response_type: 'decision',
          response_id: 'dec-batch-1',
          value: 'A',
        }),
      );

      const pollRes2 = await pendingGET(
        getRequest(`/api/dashboard/pending-responses?project_id=${PROJECT_ID}`),
      );
      const pollData2 = await jsonOf(pollRes2);

      expect(pollData2.count).toBe(3);
      const ids = pollData2.pending_responses.map((r: any) => r.id);
      expect(ids).not.toContain('dec-batch-1');
      expect(ids).toContain('dec-batch-2');
      expect(ids).toContain('apr-batch-1');
      expect(ids).toContain('err-batch-1');
    });
  });

  // -----------------------------------------------------------------------
  // Bonus: Additional edge-case coverage
  // -----------------------------------------------------------------------
  describe('Additional edge cases', () => {
    it('accepts task_completed event with success flag', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'task_completed',
        payload: {
          task_id: 99,
          task_name: 'Setup CI/CD',
          success: true,
          summary: 'GitHub Actions configured',
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(201);
      expect(data.success).toBe(true);
      expect(data.message).toContain('task_completed');
    });

    it('accepts activity event', async () => {
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'activity',
        payload: {
          activity_type: 'code_review',
          message: 'Reviewed pull request #42',
          details: { pr_number: 42, files_reviewed: 5 },
        },
      });

      const res = await eventPOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(201);
      expect(data.success).toBe(true);
    });

    it('stores agent_reasoning when provided', async () => {
      const reasoning = 'Chose this approach because of performance benefits';
      const req = postRequest('/api/dashboard/event', {
        project_id: PROJECT_ID,
        type: 'milestone',
        payload: {
          milestone_name: 'Optimization Complete',
          description: 'All performance targets met',
        },
        agent_reasoning: reasoning,
      });

      const res = await eventPOST(req);
      expect(res.status).toBe(201);

      // Verify the reasoning was stored in our mock DB
      const lastRow = dbRows[dbRows.length - 1];
      expect(lastRow.agentReasoning).toBe(reasoning);
    });

    it('handles response submission with project_id validation', async () => {
      const req = postRequest('/api/dashboard/response', {
        project_id: 'not_a_number',
        response_type: 'decision',
        response_id: 'dec-001',
        value: 'option_a',
      });

      const res = await responsePOST(req);
      const data = await jsonOf(res);

      expect(res.status).toBe(400);
      expect(data.success).toBe(false);
      expect(data.error).toContain('project_id');
    });
  });
});
