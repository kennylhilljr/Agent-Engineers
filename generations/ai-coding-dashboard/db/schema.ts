import { pgTable, text, timestamp, serial, integer, jsonb } from 'drizzle-orm/pg-core';
import { relations } from 'drizzle-orm';

/**
 * Projects table - stores AI coding project specifications
 */
export const projects = pgTable('projects', {
  id: serial('id').primaryKey(),
  name: text('name').notNull(),
  spec: text('spec').notNull(), // Project specification/description
  preferredLayout: text('preferred_layout').default('kanban'), // 'kanban' | 'table' | 'timeline'
  createdAt: timestamp('created_at').defaultNow().notNull(),
  userId: text('user_id').notNull(), // User who owns this project
});

/**
 * Tasks table - stores individual tasks within a project
 */
export const tasks = pgTable('tasks', {
  id: serial('id').primaryKey(),
  projectId: integer('project_id')
    .notNull()
    .references(() => projects.id, { onDelete: 'cascade' }),
  category: text('category').notNull(), // e.g., 'frontend', 'backend', 'testing'
  description: text('description').notNull(),
  steps: jsonb('steps').$type<string[]>().notNull(), // Array of implementation steps
  status: text('status').notNull().default('todo'), // 'todo' | 'in_progress' | 'done' | 'blocked'
  agentNotes: text('agent_notes'), // Notes from AI agent during implementation
  order: integer('order').notNull().default(0), // For ordering tasks in the UI
});

/**
 * Activity Log table - stores project activity and agent reasoning
 */
export const activityLog = pgTable('activity_log', {
  id: serial('id').primaryKey(),
  projectId: integer('project_id')
    .notNull()
    .references(() => projects.id, { onDelete: 'cascade' }),
  eventType: text('event_type').notNull(), // e.g., 'task_created', 'task_completed', 'agent_action'
  eventData: jsonb('event_data').$type<Record<string, any>>().notNull(), // Flexible event data
  agentReasoning: text('agent_reasoning'), // AI agent's reasoning for actions taken
  timestamp: timestamp('timestamp').defaultNow().notNull(),
});

/**
 * Relations for Drizzle ORM
 */
export const projectsRelations = relations(projects, ({ many }) => ({
  tasks: many(tasks),
  activityLog: many(activityLog),
}));

export const tasksRelations = relations(tasks, ({ one }) => ({
  project: one(projects, {
    fields: [tasks.projectId],
    references: [projects.id],
  }),
}));

export const activityLogRelations = relations(activityLog, ({ one }) => ({
  project: one(projects, {
    fields: [activityLog.projectId],
    references: [projects.id],
  }),
}));

// Export TypeScript types for use in the app
export type Project = typeof projects.$inferSelect;
export type NewProject = typeof projects.$inferInsert;

export type Task = typeof tasks.$inferSelect;
export type NewTask = typeof tasks.$inferInsert;

export type ActivityLog = typeof activityLog.$inferSelect;
export type NewActivityLog = typeof activityLog.$inferInsert;
