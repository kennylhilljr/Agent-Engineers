/**
 * API Type Definitions and Zod Schemas for Task Execution API
 *
 * This module provides comprehensive type-safe schemas for all API endpoints
 * including projects, tasks, execution control, events, and approvals.
 */

import { z } from 'zod';
import type { Project, Task, ActivityLog } from '@/db/schema';

/**
 * ============================================================================
 * PROJECT SCHEMAS
 * ============================================================================
 */

/**
 * Schema for creating a new project
 */
export const CreateProjectSchema = z.object({
  name: z.string().min(1, 'Project name is required').max(255),
  spec: z.string().min(1, 'Project spec is required'),
  preferredLayout: z.enum(['kanban', 'table', 'timeline']).optional().default('kanban'),
  userId: z.string().min(1, 'User ID is required'),
  specData: z.record(z.any()).optional(), // Optional structured spec data
});

export type CreateProjectRequest = z.infer<typeof CreateProjectSchema>;

/**
 * Project response type (includes computed fields)
 */
export interface ProjectResponse extends Project {
  taskCount?: number;
  completedTasks?: number;
  inProgressTasks?: number;
  todoTasks?: number;
  blockedTasks?: number;
  progress?: number; // 0-100
}

/**
 * Schema for updating a project
 */
export const UpdateProjectSchema = z.object({
  name: z.string().min(1).max(255).optional(),
  spec: z.string().min(1).optional(),
  preferredLayout: z.enum(['kanban', 'table', 'timeline']).optional(),
});

export type UpdateProjectRequest = z.infer<typeof UpdateProjectSchema>;

/**
 * ============================================================================
 * TASK SCHEMAS
 * ============================================================================
 */

/**
 * Task status enum
 */
export const TaskStatus = z.enum(['todo', 'in_progress', 'done', 'blocked']);
export type TaskStatusType = z.infer<typeof TaskStatus>;

/**
 * Schema for creating a new task
 */
export const CreateTaskSchema = z.object({
  projectId: z.number().int().positive(),
  category: z.string().min(1, 'Category is required'),
  description: z.string().min(1, 'Description is required'),
  steps: z.array(z.string()).min(1, 'At least one step is required'),
  status: TaskStatus.optional().default('todo'),
  agentNotes: z.string().optional(),
  order: z.number().int().nonnegative().optional().default(0),
});

export type CreateTaskRequest = z.infer<typeof CreateTaskSchema>;

/**
 * Schema for updating a task
 */
export const UpdateTaskSchema = z.object({
  category: z.string().min(1).optional(),
  description: z.string().min(1).optional(),
  steps: z.array(z.string()).min(1).optional(),
  status: TaskStatus.optional(),
  agentNotes: z.string().optional(),
  order: z.number().int().nonnegative().optional(),
});

export type UpdateTaskRequest = z.infer<typeof UpdateTaskSchema>;

/**
 * Schema for completing a task
 */
export const CompleteTaskSchema = z.object({
  success: z.boolean(),
  notes: z.string().optional(),
  filesChanged: z.array(z.string()).optional(),
});

export type CompleteTaskRequest = z.infer<typeof CompleteTaskSchema>;

/**
 * Task response type
 */
export interface TaskResponse extends Task {
  // Additional computed fields can be added here
}

/**
 * ============================================================================
 * EXECUTION CONTROL SCHEMAS
 * ============================================================================
 */

/**
 * Execution status enum
 */
export const ExecutionStatus = z.enum([
  'idle',
  'running',
  'paused',
  'stopped',
  'completed',
  'error'
]);
export type ExecutionStatusType = z.infer<typeof ExecutionStatus>;

/**
 * Schema for starting execution
 */
export const StartExecutionSchema = z.object({
  taskId: z.number().int().positive().optional(), // Optional: start from specific task
  autoApprove: z.boolean().optional().default(false),
  config: z.record(z.any()).optional(), // Optional execution configuration
});

export type StartExecutionRequest = z.infer<typeof StartExecutionSchema>;

/**
 * Execution response type
 */
export interface ExecutionResponse {
  status: ExecutionStatusType;
  currentTaskId?: number;
  startedAt?: string;
  pausedAt?: string;
  stoppedAt?: string;
  completedAt?: string;
  progress?: number; // 0-100
  message: string;
}

/**
 * ============================================================================
 * EVENT SCHEMAS
 * ============================================================================
 */

/**
 * Event type enum (extended from existing events.ts)
 */
export const EventType = z.enum([
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
]);
export type EventTypeType = z.infer<typeof EventType>;

/**
 * Schema for creating an event
 */
export const CreateEventSchema = z.object({
  projectId: z.number().int().positive(),
  eventType: EventType,
  eventData: z.record(z.any()),
  agentReasoning: z.string().optional(),
});

export type CreateEventRequest = z.infer<typeof CreateEventSchema>;

/**
 * Schema for querying events
 */
export const QueryEventsSchema = z.object({
  eventType: EventType.optional(),
  limit: z.number().int().positive().max(1000).optional().default(100),
  offset: z.number().int().nonnegative().optional().default(0),
  startDate: z.string().datetime().optional(),
  endDate: z.string().datetime().optional(),
});

export type QueryEventsRequest = z.infer<typeof QueryEventsSchema>;

/**
 * Event response type
 */
export interface EventResponse extends ActivityLog {
  // Additional computed fields can be added here
}

/**
 * ============================================================================
 * APPROVAL/RESPONSE SCHEMAS
 * ============================================================================
 */

/**
 * Response type enum
 */
export const ResponseType = z.enum(['decision', 'approval', 'error_recovery']);
export type ResponseTypeType = z.infer<typeof ResponseType>;

/**
 * Schema for submitting a human response
 */
export const SubmitResponseSchema = z.object({
  responseType: ResponseType,
  responseId: z.string().min(1), // decision_id, approval_id, or error_id
  value: z.any(), // decision choice, approval boolean, or recovery action
  notes: z.string().optional(),
});

export type SubmitResponseRequest = z.infer<typeof SubmitResponseSchema>;

/**
 * Pending response item
 */
export interface PendingResponseItem {
  id: string;
  responseType: ResponseTypeType;
  question?: string;
  action?: string;
  errorMessage?: string;
  options?: string[];
  priority?: 'low' | 'medium' | 'high';
  riskLevel?: 'low' | 'medium' | 'high';
  timestamp: string;
  eventData: Record<string, any>;
}

/**
 * Response submission result
 */
export interface SubmitResponseResponse {
  success: boolean;
  message: string;
  updatedEventId?: number;
}

/**
 * ============================================================================
 * COMMON API RESPONSE TYPES
 * ============================================================================
 */

/**
 * Standard success response
 */
export interface ApiSuccessResponse<T = any> {
  success: true;
  data: T;
  message?: string;
}

/**
 * Standard error response
 */
export interface ApiErrorResponse {
  success: false;
  error: string;
  details?: any;
  code?: string;
}

/**
 * Paginated response
 */
export interface PaginatedResponse<T> {
  success: true;
  data: T[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    hasMore: boolean;
  };
}

/**
 * ============================================================================
 * HELPER FUNCTIONS
 * ============================================================================
 */

/**
 * Create a success response
 */
export function successResponse<T>(data: T, message?: string): ApiSuccessResponse<T> {
  return {
    success: true,
    data,
    ...(message && { message }),
  };
}

/**
 * Create an error response
 */
export function errorResponse(error: string, details?: any, code?: string): ApiErrorResponse {
  return {
    success: false,
    error,
    ...(details && { details }),
    ...(code && { code }),
  };
}

/**
 * Create a paginated response
 */
export function paginatedResponse<T>(
  data: T[],
  total: number,
  limit: number,
  offset: number
): PaginatedResponse<T> {
  return {
    success: true,
    data,
    pagination: {
      total,
      limit,
      offset,
      hasMore: offset + data.length < total,
    },
  };
}

/**
 * Validate request body with a Zod schema
 */
export function validateRequest<T>(
  schema: z.ZodSchema<T>,
  data: unknown
): { success: true; data: T } | { success: false; error: string; details: any } {
  const result = schema.safeParse(data);
  if (result.success) {
    return { success: true, data: result.data };
  } else {
    return {
      success: false,
      error: 'Validation failed',
      details: result.error.errors,
    };
  }
}
