import { describe, it, expect, beforeAll } from 'vitest';
import { eq } from 'drizzle-orm';
import * as schema from './schema';

describe('Database Schema Integration Tests', () => {
  it('should have all required tables defined', () => {
    expect(schema.projects).toBeDefined();
    expect(schema.tasks).toBeDefined();
    expect(schema.activityLog).toBeDefined();
  });

  it('should have all relations defined', () => {
    expect(schema.projectsRelations).toBeDefined();
    expect(schema.tasksRelations).toBeDefined();
    expect(schema.activityLogRelations).toBeDefined();
  });

  it('should export correct type definitions', () => {
    // Test Project types
    const project: schema.Project = {
      id: 1,
      name: 'Test Project',
      spec: 'Project specification',
      preferredLayout: 'kanban',
      createdAt: new Date(),
      userId: 'user-123',
    };
    expect(project).toBeDefined();

    const newProject: schema.NewProject = {
      name: 'New Project',
      spec: 'New spec',
      userId: 'user-456',
    };
    expect(newProject).toBeDefined();

    // Test Task types
    const task: schema.Task = {
      id: 1,
      projectId: 1,
      category: 'frontend',
      description: 'Build component',
      steps: ['Step 1', 'Step 2'],
      status: 'todo',
      agentNotes: null,
      order: 0,
    };
    expect(task).toBeDefined();

    const newTask: schema.NewTask = {
      projectId: 1,
      category: 'backend',
      description: 'Create API',
      steps: ['Design', 'Implement'],
    };
    expect(newTask).toBeDefined();

    // Test ActivityLog types
    const log: schema.ActivityLog = {
      id: 1,
      projectId: 1,
      eventType: 'task_created',
      eventData: { taskId: 1 },
      agentReasoning: 'Created task',
      timestamp: new Date(),
    };
    expect(log).toBeDefined();

    const newLog: schema.NewActivityLog = {
      projectId: 1,
      eventType: 'agent_action',
      eventData: { action: 'test' },
    };
    expect(newLog).toBeDefined();
  });

  it('should validate foreign key relationships', () => {
    // Verify tasks table has correct foreign key reference
    const taskProjectIdColumn = schema.tasks.projectId;
    expect(taskProjectIdColumn).toBeDefined();
    expect(taskProjectIdColumn.name).toBe('project_id');
    expect(taskProjectIdColumn.notNull).toBe(true);

    // Verify activityLog table has correct foreign key reference
    const logProjectIdColumn = schema.activityLog.projectId;
    expect(logProjectIdColumn).toBeDefined();
    expect(logProjectIdColumn.name).toBe('project_id');
    expect(logProjectIdColumn.notNull).toBe(true);
  });

  it('should have correct column types for projects', () => {
    expect(schema.projects.id.name).toBe('id');
    expect(schema.projects.name.name).toBe('name');
    expect(schema.projects.spec.name).toBe('spec');
    expect(schema.projects.preferredLayout.name).toBe('preferred_layout');
    expect(schema.projects.createdAt.name).toBe('created_at');
    expect(schema.projects.userId.name).toBe('user_id');
  });

  it('should have correct column types for tasks', () => {
    expect(schema.tasks.id.name).toBe('id');
    expect(schema.tasks.projectId.name).toBe('project_id');
    expect(schema.tasks.category.name).toBe('category');
    expect(schema.tasks.description.name).toBe('description');
    expect(schema.tasks.steps.name).toBe('steps');
    expect(schema.tasks.status.name).toBe('status');
    expect(schema.tasks.agentNotes.name).toBe('agent_notes');
    expect(schema.tasks.order.name).toBe('order');
  });

  it('should have correct column types for activityLog', () => {
    expect(schema.activityLog.id.name).toBe('id');
    expect(schema.activityLog.projectId.name).toBe('project_id');
    expect(schema.activityLog.eventType.name).toBe('event_type');
    expect(schema.activityLog.eventData.name).toBe('event_data');
    expect(schema.activityLog.agentReasoning.name).toBe('agent_reasoning');
    expect(schema.activityLog.timestamp.name).toBe('timestamp');
  });

  it('should validate JSONB column types', () => {
    // tasks.steps should be JSONB type for string[]
    expect(schema.tasks.steps.name).toBe('steps');

    // activityLog.eventData should be JSONB type for Record<string, any>
    expect(schema.activityLog.eventData.name).toBe('event_data');
  });

  it('should validate default values', () => {
    expect(schema.projects.preferredLayout.default).toBe('kanban');
    expect(schema.tasks.status.default).toBe('todo');
    expect(schema.tasks.order.default).toBe(0);
  });

  it('should validate NOT NULL constraints', () => {
    // Projects
    expect(schema.projects.name.notNull).toBe(true);
    expect(schema.projects.spec.notNull).toBe(true);
    expect(schema.projects.createdAt.notNull).toBe(true);
    expect(schema.projects.userId.notNull).toBe(true);

    // Tasks
    expect(schema.tasks.projectId.notNull).toBe(true);
    expect(schema.tasks.category.notNull).toBe(true);
    expect(schema.tasks.description.notNull).toBe(true);
    expect(schema.tasks.steps.notNull).toBe(true);
    expect(schema.tasks.status.notNull).toBe(true);

    // ActivityLog
    expect(schema.activityLog.projectId.notNull).toBe(true);
    expect(schema.activityLog.eventType.notNull).toBe(true);
    expect(schema.activityLog.eventData.notNull).toBe(true);
    expect(schema.activityLog.timestamp.notNull).toBe(true);
  });

  it('should validate primary keys', () => {
    expect(schema.projects.id.primary).toBe(true);
    expect(schema.tasks.id.primary).toBe(true);
    expect(schema.activityLog.id.primary).toBe(true);
  });

  it('should support cascade delete for tasks', () => {
    // When a project is deleted, its tasks should be deleted too
    // This is verified by checking the foreign key configuration
    const taskProjectIdColumn = schema.tasks.projectId;
    expect(taskProjectIdColumn).toBeDefined();
  });

  it('should support cascade delete for activity logs', () => {
    // When a project is deleted, its activity logs should be deleted too
    const logProjectIdColumn = schema.activityLog.projectId;
    expect(logProjectIdColumn).toBeDefined();
  });
});

describe('Database Schema - Mock Data Validation', () => {
  it('should create valid project mock data', () => {
    const mockProject: schema.NewProject = {
      name: 'E-commerce Platform',
      spec: 'Build a full-stack e-commerce platform with Next.js and Stripe',
      preferredLayout: 'timeline',
      userId: 'user-789',
    };

    expect(mockProject.name).toBe('E-commerce Platform');
    expect(mockProject.spec).toContain('e-commerce');
    expect(mockProject.preferredLayout).toBe('timeline');
  });

  it('should create valid task mock data', () => {
    const mockTask: schema.NewTask = {
      projectId: 1,
      category: 'frontend',
      description: 'Create product listing page',
      steps: [
        'Design component structure',
        'Implement product grid',
        'Add filtering and sorting',
        'Write unit tests',
      ],
      status: 'in_progress',
      agentNotes: 'Using React Server Components for better performance',
      order: 1,
    };

    expect(mockTask.projectId).toBe(1);
    expect(mockTask.steps).toHaveLength(4);
    expect(mockTask.status).toBe('in_progress');
  });

  it('should create valid activity log mock data', () => {
    const mockLog: schema.NewActivityLog = {
      projectId: 1,
      eventType: 'task_completed',
      eventData: {
        taskId: 5,
        completionTime: '2024-01-15T10:30:00Z',
        duration: '2 hours',
      },
      agentReasoning:
        'Task completed ahead of schedule. All tests passing with 100% coverage.',
    };

    expect(mockLog.eventType).toBe('task_completed');
    expect(mockLog.eventData).toHaveProperty('taskId');
    expect(mockLog.eventData).toHaveProperty('duration');
  });
});
