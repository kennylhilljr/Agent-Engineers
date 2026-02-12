/**
 * Integration tests for Task Execution API endpoints
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { db } from '@/lib/db';
import { projects, tasks, activityLog } from '@/db/schema';
import { eq } from 'drizzle-orm';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000';

describe('API Integration Tests - Projects', () => {
  let testProjectId: number;
  const testUserId = 'test-user-' + Date.now();

  afterAll(async () => {
    // Clean up test data
    if (testProjectId) {
      await db.delete(projects).where(eq(projects.id, testProjectId));
    }
  });

  it('POST /api/projects - creates a new project', async () => {
    const response = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Test Project API',
        spec: 'Test specification for API integration',
        userId: testUserId,
        preferredLayout: 'kanban',
      }),
    });

    expect(response.status).toBe(201);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.name).toBe('Test Project API');
    expect(data.data.id).toBeDefined();

    testProjectId = data.data.id;
  });

  it('POST /api/projects - rejects invalid data', async () => {
    const response = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: '',
        spec: 'Test',
      }),
    });

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.success).toBe(false);
  });

  it('GET /api/projects - lists all projects', async () => {
    const response = await fetch(`${API_BASE}/api/projects`);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(Array.isArray(data.data)).toBe(true);
    expect(data.data.length).toBeGreaterThan(0);
  });

  it('GET /api/projects/[id] - gets specific project', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}`);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.id).toBe(testProjectId);
    expect(data.data.name).toBe('Test Project API');
  });

  it('GET /api/projects/[id] - returns 404 for non-existent project', async () => {
    const response = await fetch(`${API_BASE}/api/projects/999999`);

    expect(response.status).toBe(404);
    const data = await response.json();
    expect(data.success).toBe(false);
  });

  it('PATCH /api/projects/[id] - updates a project', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Updated Project Name',
        preferredLayout: 'table',
      }),
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.name).toBe('Updated Project Name');
    expect(data.data.preferredLayout).toBe('table');
  });

  it('DELETE /api/projects/[id] - deletes a project', async () => {
    // Create a temporary project to delete
    const createResponse = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Project to Delete',
        spec: 'Will be deleted',
        userId: testUserId,
      }),
    });
    const createData = await createResponse.json();
    const projectToDelete = createData.data.id;

    const response = await fetch(`${API_BASE}/api/projects/${projectToDelete}`, {
      method: 'DELETE',
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);

    // Verify deletion
    const verifyResponse = await fetch(`${API_BASE}/api/projects/${projectToDelete}`);
    expect(verifyResponse.status).toBe(404);
  });
});

describe('API Integration Tests - Tasks', () => {
  let testProjectId: number;
  let testTaskId: number;
  const testUserId = 'test-user-tasks-' + Date.now();

  beforeAll(async () => {
    // Create a test project
    const response = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Project for Task Tests',
        spec: 'Testing tasks',
        userId: testUserId,
      }),
    });
    const data = await response.json();
    testProjectId = data.data.id;
  });

  afterAll(async () => {
    if (testProjectId) {
      await db.delete(projects).where(eq(projects.id, testProjectId));
    }
  });

  it('POST /api/projects/[projectId]/tasks - creates a task', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: 'frontend',
        description: 'Build login page',
        steps: ['Create component', 'Add validation', 'Write tests'],
      }),
    });

    expect(response.status).toBe(201);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.description).toBe('Build login page');
    expect(data.data.status).toBe('todo');

    testTaskId = data.data.id;
  });

  it('POST /api/projects/[projectId]/tasks - rejects invalid task', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: 'frontend',
        description: '',
        steps: [],
      }),
    });

    expect(response.status).toBe(400);
  });

  it('GET /api/projects/[projectId]/tasks - lists tasks', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/tasks`);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(Array.isArray(data.data)).toBe(true);
    expect(data.data.length).toBeGreaterThan(0);
  });

  it('GET /api/projects/[projectId]/tasks/[taskId] - gets specific task', async () => {
    const response = await fetch(
      `${API_BASE}/api/projects/${testProjectId}/tasks/${testTaskId}`
    );

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.id).toBe(testTaskId);
  });

  it('PATCH /api/projects/[projectId]/tasks/[taskId] - updates a task', async () => {
    const response = await fetch(
      `${API_BASE}/api/projects/${testProjectId}/tasks/${testTaskId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'in_progress',
          agentNotes: 'Started working on this task',
        }),
      }
    );

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.status).toBe('in_progress');
  });

  it('POST /api/projects/[projectId]/tasks/[taskId]/complete - completes a task', async () => {
    const response = await fetch(
      `${API_BASE}/api/projects/${testProjectId}/tasks/${testTaskId}/complete`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          success: true,
          notes: 'Task completed successfully',
          filesChanged: ['login.tsx', 'auth.ts'],
        }),
      }
    );

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.status).toBe('done');
  });

  it('POST /api/projects/[projectId]/tasks/[taskId]/complete - rejects already completed task', async () => {
    const response = await fetch(
      `${API_BASE}/api/projects/${testProjectId}/tasks/${testTaskId}/complete`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          success: true,
          notes: 'Trying to complete again',
        }),
      }
    );

    expect(response.status).toBe(400);
  });

  it('DELETE /api/projects/[projectId]/tasks/[taskId] - deletes a task', async () => {
    // Create a task to delete
    const createResponse = await fetch(`${API_BASE}/api/projects/${testProjectId}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: 'backend',
        description: 'Task to delete',
        steps: ['step1'],
      }),
    });
    const createData = await createResponse.json();
    const taskToDelete = createData.data.id;

    const response = await fetch(
      `${API_BASE}/api/projects/${testProjectId}/tasks/${taskToDelete}`,
      {
        method: 'DELETE',
      }
    );

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
  });
});

describe('API Integration Tests - Execution Control', () => {
  let testProjectId: number;
  const testUserId = 'test-user-exec-' + Date.now();

  beforeAll(async () => {
    const response = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Project for Execution Tests',
        spec: 'Testing execution',
        userId: testUserId,
      }),
    });
    const data = await response.json();
    testProjectId = data.data.id;
  });

  afterAll(async () => {
    if (testProjectId) {
      await db.delete(projects).where(eq(projects.id, testProjectId));
    }
  });

  it('POST /api/projects/[projectId]/start - starts execution', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        autoApprove: false,
      }),
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.status).toBe('running');
  });

  it('GET /api/projects/[projectId]/status - gets execution status', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/status`);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.status).toBeDefined();
  });

  it('POST /api/projects/[projectId]/pause - pauses execution', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/pause`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.status).toBe('paused');
  });

  it('POST /api/projects/[projectId]/resume - resumes execution', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.status).toBe('running');
  });

  it('POST /api/projects/[projectId]/stop - stops execution', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.status).toBe('stopped');
  });
});

describe('API Integration Tests - Events', () => {
  let testProjectId: number;
  const testUserId = 'test-user-events-' + Date.now();

  beforeAll(async () => {
    const response = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Project for Event Tests',
        spec: 'Testing events',
        userId: testUserId,
      }),
    });
    const data = await response.json();
    testProjectId = data.data.id;
  });

  afterAll(async () => {
    if (testProjectId) {
      await db.delete(projects).where(eq(projects.id, testProjectId));
    }
  });

  it('POST /api/projects/[projectId]/events - creates an event', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        eventType: 'activity',
        eventData: {
          activity_type: 'test_event',
          message: 'This is a test event',
        },
        agentReasoning: 'Testing event creation',
      }),
    });

    expect(response.status).toBe(201);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.eventType).toBe('activity');
  });

  it('GET /api/projects/[projectId]/events - lists events', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/events`);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(Array.isArray(data.data)).toBe(true);
    expect(data.pagination).toBeDefined();
  });

  it('GET /api/projects/[projectId]/events - filters events by type', async () => {
    const response = await fetch(
      `${API_BASE}/api/projects/${testProjectId}/events?eventType=activity&limit=10`
    );

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
  });

  it('GET /api/projects/[projectId]/events - validates pagination parameters', async () => {
    const response = await fetch(
      `${API_BASE}/api/projects/${testProjectId}/events?limit=2000`
    );

    expect(response.status).toBe(400);
  });
});

describe('API Integration Tests - Responses', () => {
  let testProjectId: number;
  const testUserId = 'test-user-responses-' + Date.now();

  beforeAll(async () => {
    const response = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Project for Response Tests',
        spec: 'Testing responses',
        userId: testUserId,
      }),
    });
    const data = await response.json();
    testProjectId = data.data.id;

    // Create a decision_needed event
    await fetch(`${API_BASE}/api/projects/${testProjectId}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        eventType: 'decision_needed',
        eventData: {
          decision_id: 'test-decision-123',
          question: 'Which framework to use?',
          options: ['React', 'Vue', 'Angular'],
          priority: 'high',
        },
        agentReasoning: 'Need to choose framework',
      }),
    });
  });

  afterAll(async () => {
    if (testProjectId) {
      await db.delete(projects).where(eq(projects.id, testProjectId));
    }
  });

  it('GET /api/projects/[projectId]/pending-responses - lists pending responses', async () => {
    const response = await fetch(
      `${API_BASE}/api/projects/${testProjectId}/pending-responses`
    );

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.pendingResponses).toBeDefined();
    expect(data.data.count).toBeGreaterThan(0);
  });

  it('POST /api/projects/[projectId]/responses - submits a response', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/responses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        responseType: 'decision',
        responseId: 'test-decision-123',
        value: 'React',
        notes: 'React is the best choice',
      }),
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
  });

  it('POST /api/projects/[projectId]/responses - rejects duplicate response', async () => {
    const response = await fetch(`${API_BASE}/api/projects/${testProjectId}/responses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        responseType: 'decision',
        responseId: 'test-decision-123',
        value: 'Vue',
        notes: 'Trying to respond again',
      }),
    });

    expect(response.status).toBe(400);
  });
});

describe('API Integration Tests - Error Handling', () => {
  it('handles invalid project ID format', async () => {
    const response = await fetch(`${API_BASE}/api/projects/invalid-id`);
    expect(response.status).toBe(400);
  });

  it('handles invalid JSON in request body', async () => {
    const response = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: 'invalid json',
    });
    expect(response.status).toBe(400);
  });

  it('handles missing required fields', async () => {
    const response = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    expect(response.status).toBe(400);
  });
});
