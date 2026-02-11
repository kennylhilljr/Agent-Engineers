import { describe, it, expect } from 'vitest';
import {
  projects,
  tasks,
  activityLog,
  projectsRelations,
  tasksRelations,
  activityLogRelations,
  type Project,
  type NewProject,
  type Task,
  type NewTask,
  type ActivityLog,
  type NewActivityLog,
} from './schema';

describe('Database Schema - Projects Table', () => {
  it('should have correct table structure', () => {
    expect(projects).toBeDefined();
    expect(projects.id).toBeDefined();
    expect(projects.name).toBeDefined();
    expect(projects.spec).toBeDefined();
    expect(projects.preferredLayout).toBeDefined();
    expect(projects.createdAt).toBeDefined();
    expect(projects.userId).toBeDefined();
  });

  it('should have serial primary key id', () => {
    expect(projects.id.name).toBe('id');
    expect(projects.id.primary).toBe(true);
  });

  it('should have required fields marked as not null', () => {
    expect(projects.name.notNull).toBe(true);
    expect(projects.spec.notNull).toBe(true);
    expect(projects.createdAt.notNull).toBe(true);
    expect(projects.userId.notNull).toBe(true);
  });

  it('should have default value for preferredLayout', () => {
    expect(projects.preferredLayout.default).toBe('kanban');
  });

  it('should export correct TypeScript types', () => {
    // Type checks - these will fail at compile time if types are wrong
    const mockProject: Project = {
      id: 1,
      name: 'Test Project',
      spec: 'A test project specification',
      preferredLayout: 'kanban',
      createdAt: new Date(),
      userId: 'user-123',
    };

    const mockNewProject: NewProject = {
      name: 'New Project',
      spec: 'Project spec',
      userId: 'user-456',
    };

    expect(mockProject).toBeDefined();
    expect(mockNewProject).toBeDefined();
  });
});

describe('Database Schema - Tasks Table', () => {
  it('should have correct table structure', () => {
    expect(tasks).toBeDefined();
    expect(tasks.id).toBeDefined();
    expect(tasks.projectId).toBeDefined();
    expect(tasks.category).toBeDefined();
    expect(tasks.description).toBeDefined();
    expect(tasks.steps).toBeDefined();
    expect(tasks.status).toBeDefined();
    expect(tasks.agentNotes).toBeDefined();
    expect(tasks.order).toBeDefined();
  });

  it('should have serial primary key id', () => {
    expect(tasks.id.name).toBe('id');
    expect(tasks.id.primary).toBe(true);
  });

  it('should have foreign key to projects', () => {
    expect(tasks.projectId.name).toBe('project_id');
    expect(tasks.projectId.notNull).toBe(true);
  });

  it('should have required fields marked as not null', () => {
    expect(tasks.projectId.notNull).toBe(true);
    expect(tasks.category.notNull).toBe(true);
    expect(tasks.description.notNull).toBe(true);
    expect(tasks.steps.notNull).toBe(true);
    expect(tasks.status.notNull).toBe(true);
  });

  it('should have default values', () => {
    expect(tasks.status.default).toBe('todo');
    expect(tasks.order.default).toBe(0);
  });

  it('should export correct TypeScript types', () => {
    const mockTask: Task = {
      id: 1,
      projectId: 1,
      category: 'frontend',
      description: 'Build UI component',
      steps: ['Step 1', 'Step 2'],
      status: 'todo',
      agentNotes: 'Some notes',
      order: 0,
    };

    const mockNewTask: NewTask = {
      projectId: 1,
      category: 'backend',
      description: 'Create API endpoint',
      steps: ['Design API', 'Implement'],
    };

    expect(mockTask).toBeDefined();
    expect(mockNewTask).toBeDefined();
  });
});

describe('Database Schema - ActivityLog Table', () => {
  it('should have correct table structure', () => {
    expect(activityLog).toBeDefined();
    expect(activityLog.id).toBeDefined();
    expect(activityLog.projectId).toBeDefined();
    expect(activityLog.eventType).toBeDefined();
    expect(activityLog.eventData).toBeDefined();
    expect(activityLog.agentReasoning).toBeDefined();
    expect(activityLog.timestamp).toBeDefined();
  });

  it('should have serial primary key id', () => {
    expect(activityLog.id.name).toBe('id');
    expect(activityLog.id.primary).toBe(true);
  });

  it('should have foreign key to projects', () => {
    expect(activityLog.projectId.name).toBe('project_id');
    expect(activityLog.projectId.notNull).toBe(true);
  });

  it('should have required fields marked as not null', () => {
    expect(activityLog.projectId.notNull).toBe(true);
    expect(activityLog.eventType.notNull).toBe(true);
    expect(activityLog.eventData.notNull).toBe(true);
    expect(activityLog.timestamp.notNull).toBe(true);
  });

  it('should export correct TypeScript types', () => {
    const mockLog: ActivityLog = {
      id: 1,
      projectId: 1,
      eventType: 'task_created',
      eventData: { taskId: 1, name: 'New Task' },
      agentReasoning: 'Created task based on user request',
      timestamp: new Date(),
    };

    const mockNewLog: NewActivityLog = {
      projectId: 1,
      eventType: 'agent_action',
      eventData: { action: 'code_generated' },
    };

    expect(mockLog).toBeDefined();
    expect(mockNewLog).toBeDefined();
  });
});

describe('Database Schema - Relations', () => {
  it('should define projects relations', () => {
    expect(projectsRelations).toBeDefined();
  });

  it('should define tasks relations', () => {
    expect(tasksRelations).toBeDefined();
  });

  it('should define activityLog relations', () => {
    expect(activityLogRelations).toBeDefined();
  });
});

describe('Database Schema - Type Safety', () => {
  it('should enforce type safety for Project', () => {
    const validProject: NewProject = {
      name: 'Test',
      spec: 'Spec',
      userId: 'user-1',
      preferredLayout: 'table',
    };

    expect(validProject.name).toBe('Test');
    expect(validProject.spec).toBe('Spec');
    expect(validProject.userId).toBe('user-1');
  });

  it('should enforce type safety for Task', () => {
    const validTask: NewTask = {
      projectId: 1,
      category: 'testing',
      description: 'Write tests',
      steps: ['Unit tests', 'Integration tests'],
      status: 'in_progress',
      order: 5,
    };

    expect(validTask.projectId).toBe(1);
    expect(validTask.steps).toEqual(['Unit tests', 'Integration tests']);
  });

  it('should enforce type safety for ActivityLog', () => {
    const validLog: NewActivityLog = {
      projectId: 1,
      eventType: 'task_completed',
      eventData: { taskId: 5, duration: '2h' },
      agentReasoning: 'Task completed successfully',
    };

    expect(validLog.eventType).toBe('task_completed');
    expect(validLog.eventData).toHaveProperty('taskId');
  });
});
