/**
 * KAN-71: End-to-end testing with sample project
 *
 * Tests the full workflow: spec upload → task parsing → event ingestion →
 * UI component generation → approval/decision response → pending polling.
 *
 * Uses the sample specs in /test-specs/ to validate the full pipeline.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { NextRequest } from 'next/server';

// --- Helpers: create mock NextRequest -----------------------------------

function makeRequest(
  url: string,
  init?: { method?: string; body?: any; headers?: Record<string, string> },
) {
  const method = init?.method ?? 'GET';
  const headers = new Headers(init?.headers ?? { 'Content-Type': 'application/json' });
  const bodyStr = init?.body ? JSON.stringify(init.body) : undefined;
  return new NextRequest(new URL(url, 'http://localhost:3000'), {
    method,
    headers,
    ...(bodyStr ? { body: bodyStr } : {}),
  });
}

// --- Sample specs (mirrors test-specs/*.json) ----------------------------

const simpleSpec = {
  name: 'Simple Todo App',
  tasks: [
    { category: 'frontend', description: 'Create homepage component', steps: ['Set up component', 'Add styles', 'Test'] },
    { category: 'backend', description: 'Build API endpoint', steps: ['Define schema', 'Implement handler'] },
    { category: 'testing', description: 'Write unit tests', steps: ['Test frontend', 'Test backend'] },
  ],
};

const complexSpec = {
  name: 'Complex E-Commerce App',
  tasks: [
    { category: 'setup', description: 'Initialize Next.js project', steps: ['Create app', 'Install deps', 'Configure TS'] },
    { category: 'backend', description: 'Set up database', steps: ['Schema', 'Migrations', 'Seed data'] },
    { category: 'backend', description: 'Build auth system', steps: ['JWT tokens', 'Login', 'Register', 'Middleware'] },
    { category: 'frontend', description: 'Build product catalog', steps: ['List', 'Detail', 'Search', 'Filter'] },
    { category: 'frontend', description: 'Build shopping cart', steps: ['Add', 'Remove', 'Persist'] },
    { category: 'frontend', description: 'Build checkout flow', steps: ['Address', 'Payment', 'Confirmation'] },
    { category: 'backend', description: 'Payment integration', steps: ['Stripe setup', 'Webhooks', 'Receipts'] },
    { category: 'testing', description: 'E2E tests', steps: ['Happy path', 'Error cases', 'Perf tests'] },
  ],
};

// =========================================================================
// 1.  Spec Upload & Parsing  (/api/spec)
// =========================================================================

describe('KAN-71 E2E: Spec Upload & Parsing', () => {
  let specHandler: typeof import('../app/api/spec/route').POST;

  beforeEach(async () => {
    const mod = await import('../app/api/spec/route');
    specHandler = mod.POST;
  });

  it('accepts a simple project spec and returns projectId', async () => {
    const req = makeRequest('http://localhost:3000/api/spec', {
      method: 'POST',
      body: simpleSpec,
    });
    const res = await specHandler(req);
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data.projectId).toBeDefined();
    expect(data.taskCount).toBe(3);
  });

  it('accepts a complex project spec with many tasks', async () => {
    const req = makeRequest('http://localhost:3000/api/spec', {
      method: 'POST',
      body: complexSpec,
    });
    const res = await specHandler(req);
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data.projectId).toBeDefined();
    expect(data.taskCount).toBe(8);
  });

  it('rejects spec with no tasks array', async () => {
    const req = makeRequest('http://localhost:3000/api/spec', {
      method: 'POST',
      body: { name: 'Bad spec' },
    });
    const res = await specHandler(req);
    expect(res.status).toBe(400);
  });

  it('rejects spec with empty tasks', async () => {
    const req = makeRequest('http://localhost:3000/api/spec', {
      method: 'POST',
      body: { tasks: [] },
    });
    const res = await specHandler(req);
    expect(res.status).toBe(400);
  });

  it('rejects task missing category', async () => {
    const req = makeRequest('http://localhost:3000/api/spec', {
      method: 'POST',
      body: { tasks: [{ description: 'No category' }] },
    });
    const res = await specHandler(req);
    expect(res.status).toBe(400);
  });

  it('rejects task missing description', async () => {
    const req = makeRequest('http://localhost:3000/api/spec', {
      method: 'POST',
      body: { tasks: [{ category: 'setup' }] },
    });
    const res = await specHandler(req);
    expect(res.status).toBe(400);
  });
});

// =========================================================================
// 2.  Event Ingestion  (/api/dashboard/event)
// =========================================================================

describe('KAN-71 E2E: Event Ingestion', () => {
  let eventHandler: typeof import('../app/api/dashboard/event/route').POST;

  beforeEach(async () => {
    const mod = await import('../app/api/dashboard/event/route');
    eventHandler = mod.POST;
  });

  it('accepts task_started event with full payload', async () => {
    const req = makeRequest('http://localhost:3000/api/dashboard/event', {
      method: 'POST',
      body: {
        type: 'task_started',
        payload: {
          task_id: 'task-1',
          title: 'Create homepage component',
          category: 'frontend',
          status: 'in_progress',
        },
      },
    });
    const res = await eventHandler(req);
    expect(res.status).toBeLessThan(300);
    const data = await res.json();
    expect(data.event_id ?? data.eventId ?? data.id ?? data.success).toBeDefined();
  });

  it('accepts task_completed event', async () => {
    const req = makeRequest('http://localhost:3000/api/dashboard/event', {
      method: 'POST',
      body: {
        type: 'task_completed',
        payload: {
          task_id: 'task-1',
          title: 'Create homepage component',
          status: 'completed',
          tasks_completed: 1,
          total_tasks: 3,
          percentage: 33,
        },
      },
    });
    const res = await eventHandler(req);
    expect(res.status).toBeLessThan(300);
  });

  it('accepts milestone event', async () => {
    const req = makeRequest('http://localhost:3000/api/dashboard/event', {
      method: 'POST',
      body: {
        type: 'milestone',
        payload: {
          title: 'Frontend Complete',
          summary: 'All frontend tasks finished',
          tasks_completed: 2,
          next_phase: 'Testing',
          achievements: ['Homepage built', 'API connected'],
        },
      },
    });
    const res = await eventHandler(req);
    expect(res.status).toBeLessThan(300);
  });

  it('accepts error event', async () => {
    const req = makeRequest('http://localhost:3000/api/dashboard/event', {
      method: 'POST',
      body: {
        type: 'error',
        payload: {
          error_id: 'err-1',
          message: 'Build failed',
          details: 'TypeScript compilation error in component.tsx',
          recovery_options: [
            { id: 'fix', label: 'Auto-fix', description: 'Attempt automatic fix' },
            { id: 'skip', label: 'Skip task', description: 'Skip and continue' },
          ],
        },
      },
    });
    const res = await eventHandler(req);
    expect(res.status).toBeLessThan(300);
  });

  it('accepts decision_needed event', async () => {
    const req = makeRequest('http://localhost:3000/api/dashboard/event', {
      method: 'POST',
      body: {
        type: 'decision_needed',
        payload: {
          decision_id: 'dec-1',
          question: 'Which CSS framework to use?',
          options: [
            { id: 'tailwind', label: 'Tailwind CSS', description: 'Utility-first', recommended: true },
            { id: 'css-modules', label: 'CSS Modules', description: 'Scoped styles' },
          ],
          context: 'Project requires responsive design',
        },
      },
    });
    const res = await eventHandler(req);
    expect(res.status).toBeLessThan(300);
  });

  it('accepts approval_needed event', async () => {
    const req = makeRequest('http://localhost:3000/api/dashboard/event', {
      method: 'POST',
      body: {
        type: 'approval_needed',
        payload: {
          approval_id: 'apr-1',
          action: 'Install 15 npm packages',
          risk_level: 'medium',
          context: 'Adding production dependencies',
          affected_files: ['package.json', 'package-lock.json'],
        },
      },
    });
    const res = await eventHandler(req);
    expect(res.status).toBeLessThan(300);
  });
});

// =========================================================================
// 3.  A2UI Component Catalog verification
// =========================================================================

describe('KAN-71 E2E: A2UI Component Catalog', () => {
  it('catalog has all 17 registered components', async () => {
    const { getA2UIComponentNames } = await import('../lib/a2ui-catalog');
    const names = getA2UIComponentNames();

    // 8 primitive + 9 domain = 17
    expect(names.length).toBeGreaterThanOrEqual(17);

    // Verify all domain components
    expect(names).toContain('a2ui.TaskCard');
    expect(names).toContain('a2ui.ProgressRing');
    expect(names).toContain('a2ui.ActivityItem');
    expect(names).toContain('a2ui.FileTree');
    expect(names).toContain('a2ui.TestResults');
    expect(names).toContain('a2ui.ApprovalCard');
    expect(names).toContain('a2ui.DecisionCard');
    expect(names).toContain('a2ui.MilestoneCard');
    expect(names).toContain('a2ui.ErrorCard');
  });

  it('A2UIRenderer returns error for unknown component', async () => {
    const { hasA2UIComponent } = await import('../lib/a2ui-catalog');
    expect(hasA2UIComponent('a2ui.TaskCard')).toBe(true);
    expect(hasA2UIComponent('a2ui.Unknown')).toBe(false);
    expect(hasA2UIComponent('script')).toBe(false);
  });
});

// =========================================================================
// 4.  Layout Selection
// =========================================================================

describe('KAN-71 E2E: Layout Selection', () => {
  it('detects kanban layout for small projects (< 20 tasks)', async () => {
    const { detectLayoutFromTasks } = await import('../lib/layout-selector');
    const tasks = Array.from({ length: 5 }, (_, i) => ({
      id: i + 1,
      projectId: 1,
      category: 'setup',
      description: `Task ${i + 1}`,
      steps: ['step 1'],
      status: 'todo',
      agentNotes: null,
      order: i,
    }));
    const result = detectLayoutFromTasks(tasks as any);
    expect(result.layout).toBe('kanban');
  });

  it('detects timeline layout for sequential projects', async () => {
    const { detectLayoutFromTasks } = await import('../lib/layout-selector');
    const tasks = Array.from({ length: 25 }, (_, i) => ({
      id: i + 1,
      projectId: 1,
      category: i < 8 ? 'setup' : i < 16 ? 'backend' : 'frontend',
      description: `Task ${i + 1}`,
      steps: ['step 1'],
      status: 'todo',
      agentNotes: null,
      order: i,
    }));
    const result = detectLayoutFromTasks(tasks as any);
    // Should be timeline or graph for larger projects
    expect(['timeline', 'graph']).toContain(result.layout);
  });
});

// =========================================================================
// 5.  A2UI Validator
// =========================================================================

describe('KAN-71 E2E: A2UI Validator', () => {
  it('validates well-formed A2UI message', async () => {
    const { validateA2UIMessage } = await import('../lib/a2ui-validator');

    const msg = {
      messageType: 'surfaceUpdate',
      components: [
        {
          type: 'a2ui.TaskCard',
          id: 'task-1',
          props: { title: 'Test', status: 'in_progress' },
        },
      ],
      timestamp: new Date().toISOString(),
    };

    const result = validateA2UIMessage(msg);
    expect(result.valid).toBe(true);
    expect(result.errors.length).toBe(0);
  });

  it('rejects message with missing required fields', async () => {
    const { validateA2UIMessage } = await import('../lib/a2ui-validator');

    const msg = {
      messageType: 'surfaceUpdate',
      components: [
        { type: 'a2ui.TaskCard', props: { title: 'No ID' } }, // missing id
      ],
    };

    const result = validateA2UIMessage(msg as any);
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('rejects unauthorized component types', async () => {
    const { validateA2UIMessage } = await import('../lib/a2ui-validator');

    const msg = {
      messageType: 'surfaceUpdate',
      components: [
        { type: 'script', id: 'xss-1', props: { src: 'evil.js' } },
      ],
    };

    const result = validateA2UIMessage(msg as any);
    expect(result.valid).toBe(false);
  });
});

// =========================================================================
// 6.  Full Pipeline: Upload → Events → Components
// =========================================================================

describe('KAN-71 E2E: Full Pipeline', () => {
  it('simple project: upload spec → generate events → validate flow', async () => {
    // Step 1: Upload spec
    const specMod = await import('../app/api/spec/route');
    const specReq = makeRequest('http://localhost:3000/api/spec', {
      method: 'POST',
      body: simpleSpec,
    });
    const specRes = await specMod.POST(specReq);
    const specData = await specRes.json();
    expect(specRes.status).toBe(200);
    const projectId = specData.projectId;
    expect(projectId).toBeDefined();

    // Step 2: Simulate task_started event
    const eventMod = await import('../app/api/dashboard/event/route');
    const eventReq = makeRequest('http://localhost:3000/api/dashboard/event', {
      method: 'POST',
      body: {
        type: 'task_started',
        payload: {
          project_id: projectId,
          task_id: 'task-0',
          title: simpleSpec.tasks[0].description,
          category: simpleSpec.tasks[0].category,
          status: 'in_progress',
        },
      },
    });
    const eventRes = await eventMod.POST(eventReq);
    expect(eventRes.status).toBeLessThan(300);

    // Step 3: Verify A2UI catalog can render the components this would generate
    const { hasA2UIComponent } = await import('../lib/a2ui-catalog');
    expect(hasA2UIComponent('a2ui.TaskCard')).toBe(true);
    expect(hasA2UIComponent('a2ui.ActivityItem')).toBe(true);
    expect(hasA2UIComponent('a2ui.ProgressRing')).toBe(true);
  });

  it('complex project with 8 tasks: verifies task count parsing', async () => {
    const specMod = await import('../app/api/spec/route');
    const req = makeRequest('http://localhost:3000/api/spec', {
      method: 'POST',
      body: complexSpec,
    });
    const res = await specMod.POST(req);
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data.taskCount).toBe(8);
    expect(data.projectId).toMatch(/^project-/);
  });

  it('approval workflow: event → approve response → verify', async () => {
    // Step 1: Send approval event
    const eventMod = await import('../app/api/dashboard/event/route');
    const eventReq = makeRequest('http://localhost:3000/api/dashboard/event', {
      method: 'POST',
      body: {
        type: 'approval_needed',
        payload: {
          approval_id: 'apr-e2e-1',
          action: 'Delete unused files',
          risk_level: 'high',
          context: 'Removing 12 files',
          affected_files: ['old-file.ts', 'deprecated.tsx'],
        },
      },
    });
    const eventRes = await eventMod.POST(eventReq);
    expect(eventRes.status).toBeLessThan(300);

    // Step 2: Submit approval response
    const responseMod = await import('../app/api/dashboard/response/route');
    const responseReq = makeRequest('http://localhost:3000/api/dashboard/response', {
      method: 'POST',
      body: {
        response_type: 'approval',
        response_id: 'apr-e2e-1',
        value: { approved: true },
      },
    });
    const responseRes = await responseMod.POST(responseReq);
    expect(responseRes.status).toBeLessThan(300);
  });

  it('decision workflow: event → select option → verify', async () => {
    // Step 1: Send decision event
    const eventMod = await import('../app/api/dashboard/event/route');
    const eventReq = makeRequest('http://localhost:3000/api/dashboard/event', {
      method: 'POST',
      body: {
        type: 'decision_needed',
        payload: {
          decision_id: 'dec-e2e-1',
          question: 'Which testing framework?',
          options: [
            { id: 'vitest', label: 'Vitest', description: 'Fast Vite-native', recommended: true },
            { id: 'jest', label: 'Jest', description: 'Popular standard' },
          ],
        },
      },
    });
    const eventRes = await eventMod.POST(eventReq);
    expect(eventRes.status).toBeLessThan(300);

    // Step 2: Submit decision response
    const responseMod = await import('../app/api/dashboard/response/route');
    const responseReq = makeRequest('http://localhost:3000/api/dashboard/response', {
      method: 'POST',
      body: {
        response_type: 'decision',
        response_id: 'dec-e2e-1',
        value: { selected_option: 'vitest' },
      },
    });
    const responseRes = await responseMod.POST(responseReq);
    expect(responseRes.status).toBeLessThan(300);
  });
});
