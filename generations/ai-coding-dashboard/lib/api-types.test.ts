/**
 * Unit tests for API types and validation schemas
 */

import { describe, it, expect } from 'vitest';
import {
  CreateProjectSchema,
  UpdateProjectSchema,
  CreateTaskSchema,
  UpdateTaskSchema,
  CompleteTaskSchema,
  StartExecutionSchema,
  QueryEventsSchema,
  CreateEventSchema,
  SubmitResponseSchema,
  TaskStatus,
  ExecutionStatus,
  EventType,
  ResponseType,
  successResponse,
  errorResponse,
  paginatedResponse,
  validateRequest,
} from './api-types';

describe('API Types - Project Schemas', () => {
  it('validates CreateProjectSchema with valid data', () => {
    const validData = {
      name: 'Test Project',
      spec: 'This is a test project spec',
      preferredLayout: 'kanban' as const,
      userId: 'user-123',
    };

    const result = CreateProjectSchema.safeParse(validData);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.name).toBe('Test Project');
      expect(result.data.preferredLayout).toBe('kanban');
    }
  });

  it('rejects CreateProjectSchema with empty name', () => {
    const invalidData = {
      name: '',
      spec: 'Test spec',
      userId: 'user-123',
    };

    const result = CreateProjectSchema.safeParse(invalidData);
    expect(result.success).toBe(false);
  });

  it('applies default preferredLayout in CreateProjectSchema', () => {
    const data = {
      name: 'Test Project',
      spec: 'Test spec',
      userId: 'user-123',
    };

    const result = CreateProjectSchema.safeParse(data);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.preferredLayout).toBe('kanban');
    }
  });

  it('validates UpdateProjectSchema with partial data', () => {
    const validData = {
      name: 'Updated Project Name',
    };

    const result = UpdateProjectSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });

  it('accepts all layout types in UpdateProjectSchema', () => {
    const layouts = ['kanban', 'table', 'timeline'];

    layouts.forEach((layout) => {
      const result = UpdateProjectSchema.safeParse({ preferredLayout: layout });
      expect(result.success).toBe(true);
    });
  });
});

describe('API Types - Task Schemas', () => {
  it('validates CreateTaskSchema with valid data', () => {
    const validData = {
      projectId: 1,
      category: 'frontend',
      description: 'Build login page',
      steps: ['Create component', 'Add validation', 'Test'],
    };

    const result = CreateTaskSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });

  it('rejects CreateTaskSchema with negative projectId', () => {
    const invalidData = {
      projectId: -1,
      category: 'frontend',
      description: 'Test',
      steps: ['step1'],
    };

    const result = CreateTaskSchema.safeParse(invalidData);
    expect(result.success).toBe(false);
  });

  it('rejects CreateTaskSchema with empty steps array', () => {
    const invalidData = {
      projectId: 1,
      category: 'frontend',
      description: 'Test',
      steps: [],
    };

    const result = CreateTaskSchema.safeParse(invalidData);
    expect(result.success).toBe(false);
  });

  it('applies default status in CreateTaskSchema', () => {
    const data = {
      projectId: 1,
      category: 'frontend',
      description: 'Test',
      steps: ['step1'],
    };

    const result = CreateTaskSchema.safeParse(data);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.status).toBe('todo');
      expect(result.data.order).toBe(0);
    }
  });

  it('validates all TaskStatus values', () => {
    const statuses = ['todo', 'in_progress', 'done', 'blocked'];

    statuses.forEach((status) => {
      const result = TaskStatus.safeParse(status);
      expect(result.success).toBe(true);
    });
  });

  it('validates UpdateTaskSchema with partial data', () => {
    const validData = {
      status: 'done' as const,
      agentNotes: 'Completed successfully',
    };

    const result = UpdateTaskSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });

  it('validates CompleteTaskSchema', () => {
    const validData = {
      success: true,
      notes: 'Task completed',
      filesChanged: ['file1.ts', 'file2.ts'],
    };

    const result = CompleteTaskSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });
});

describe('API Types - Execution Schemas', () => {
  it('validates StartExecutionSchema with minimal data', () => {
    const validData = {};

    const result = StartExecutionSchema.safeParse(validData);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.autoApprove).toBe(false);
    }
  });

  it('validates StartExecutionSchema with full data', () => {
    const validData = {
      taskId: 5,
      autoApprove: true,
      config: { timeout: 3600 },
    };

    const result = StartExecutionSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });

  it('validates all ExecutionStatus values', () => {
    const statuses = ['idle', 'running', 'paused', 'stopped', 'completed', 'error'];

    statuses.forEach((status) => {
      const result = ExecutionStatus.safeParse(status);
      expect(result.success).toBe(true);
    });
  });
});

describe('API Types - Event Schemas', () => {
  it('validates CreateEventSchema', () => {
    const validData = {
      projectId: 1,
      eventType: 'task_started' as const,
      eventData: { taskId: 5, taskName: 'Test task' },
      agentReasoning: 'Starting task execution',
    };

    const result = CreateEventSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });

  it('validates all EventType values', () => {
    const eventTypes = [
      'task_started',
      'task_completed',
      'decision_needed',
      'approval_needed',
      'error',
      'milestone',
      'file_changed',
      'activity',
      'project_created',
      'project_updated',
      'task_created',
      'task_updated',
      'execution_started',
      'execution_paused',
      'execution_resumed',
      'execution_stopped',
      'execution_completed',
    ];

    eventTypes.forEach((eventType) => {
      const result = EventType.safeParse(eventType);
      expect(result.success).toBe(true);
    });
  });

  it('validates QueryEventsSchema with default values', () => {
    const result = QueryEventsSchema.safeParse({});
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.limit).toBe(100);
      expect(result.data.offset).toBe(0);
    }
  });

  it('rejects QueryEventsSchema with limit > 1000', () => {
    const result = QueryEventsSchema.safeParse({ limit: 1001 });
    expect(result.success).toBe(false);
  });

  it('validates QueryEventsSchema with date filters', () => {
    const validData = {
      startDate: '2024-01-01T00:00:00Z',
      endDate: '2024-12-31T23:59:59Z',
    };

    const result = QueryEventsSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });
});

describe('API Types - Response Schemas', () => {
  it('validates SubmitResponseSchema for decision', () => {
    const validData = {
      responseType: 'decision' as const,
      responseId: 'dec-123',
      value: 'option-a',
      notes: 'Choosing option A',
    };

    const result = SubmitResponseSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });

  it('validates SubmitResponseSchema for approval', () => {
    const validData = {
      responseType: 'approval' as const,
      responseId: 'app-456',
      value: true,
    };

    const result = SubmitResponseSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });

  it('validates all ResponseType values', () => {
    const responseTypes = ['decision', 'approval', 'error_recovery'];

    responseTypes.forEach((responseType) => {
      const result = ResponseType.safeParse(responseType);
      expect(result.success).toBe(true);
    });
  });
});

describe('API Types - Helper Functions', () => {
  it('creates success response', () => {
    const data = { id: 1, name: 'Test' };
    const response = successResponse(data, 'Success message');

    expect(response.success).toBe(true);
    expect(response.data).toEqual(data);
    expect(response.message).toBe('Success message');
  });

  it('creates success response without message', () => {
    const data = { id: 1 };
    const response = successResponse(data);

    expect(response.success).toBe(true);
    expect(response.data).toEqual(data);
    expect(response.message).toBeUndefined();
  });

  it('creates error response', () => {
    const response = errorResponse('Error message', { field: 'invalid' }, 'ERR_001');

    expect(response.success).toBe(false);
    expect(response.error).toBe('Error message');
    expect(response.details).toEqual({ field: 'invalid' });
    expect(response.code).toBe('ERR_001');
  });

  it('creates paginated response', () => {
    const data = [{ id: 1 }, { id: 2 }, { id: 3 }];
    const response = paginatedResponse(data, 10, 3, 0);

    expect(response.success).toBe(true);
    expect(response.data).toEqual(data);
    expect(response.pagination.total).toBe(10);
    expect(response.pagination.limit).toBe(3);
    expect(response.pagination.offset).toBe(0);
    expect(response.pagination.hasMore).toBe(true);
  });

  it('calculates hasMore correctly in paginated response', () => {
    const data = [{ id: 1 }, { id: 2 }];
    const response = paginatedResponse(data, 2, 10, 0);

    expect(response.pagination.hasMore).toBe(false);
  });

  it('validates request successfully', () => {
    const schema = CreateProjectSchema;
    const data = {
      name: 'Test Project',
      spec: 'Test spec',
      userId: 'user-123',
    };

    const result = validateRequest(schema, data);

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.name).toBe('Test Project');
    }
  });

  it('validates request with failure', () => {
    const schema = CreateProjectSchema;
    const data = {
      name: '',
      spec: 'Test spec',
    };

    const result = validateRequest(schema, data);

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error).toBe('Validation failed');
      expect(result.details).toBeDefined();
    }
  });
});
