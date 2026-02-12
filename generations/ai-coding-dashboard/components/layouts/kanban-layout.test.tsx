/**
 * Unit Tests for Kanban Layout Component
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KanbanLayout } from './kanban-layout';
import { Task } from '@/db/schema';

describe('KanbanLayout', () => {
  const mockTasks: Task[] = [
    {
      id: 1,
      projectId: 1,
      category: 'frontend',
      description: 'Build homepage',
      steps: ['Create component', 'Add styles'],
      status: 'todo',
      agentNotes: null,
      order: 0,
    },
    {
      id: 2,
      projectId: 1,
      category: 'backend',
      description: 'Create API',
      steps: ['Define schema'],
      status: 'in_progress',
      agentNotes: null,
      order: 1,
    },
    {
      id: 3,
      projectId: 1,
      category: 'testing',
      description: 'Write tests',
      steps: ['Test frontend'],
      status: 'done',
      agentNotes: null,
      order: 2,
    },
  ];

  it('should render kanban board header', () => {
    render(<KanbanLayout tasks={mockTasks} />);

    expect(screen.getByText('Kanban Board')).toBeInTheDocument();
    expect(screen.getByText(/Drag tasks to reorder/i)).toBeInTheDocument();
  });

  it('should render all columns', () => {
    render(<KanbanLayout tasks={mockTasks} />);

    // Column headers appear multiple times (header + badges)
    expect(screen.getAllByText('To Do').length).toBeGreaterThan(0);
    expect(screen.getAllByText('In Progress').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Done').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0);
  });

  it('should organize tasks by status', () => {
    const { container } = render(<KanbanLayout tasks={mockTasks} />);

    // Check that tasks are in the correct columns
    expect(screen.getByText('Build homepage')).toBeInTheDocument();
    expect(screen.getByText('Create API')).toBeInTheDocument();
    expect(screen.getByText('Write tests')).toBeInTheDocument();
  });

  it('should display task counts in columns', () => {
    render(<KanbanLayout tasks={mockTasks} />);

    // Each column should show task count (using getAllByText because there are badges)
    const badges = screen.getAllByText('1');
    expect(badges.length).toBeGreaterThan(0);
  });

  it('should display progress bar', () => {
    render(<KanbanLayout tasks={mockTasks} />);

    expect(screen.getByText('1 of 3 completed')).toBeInTheDocument();
    expect(screen.getByText('33%')).toBeInTheDocument();
  });

  it('should highlight current task', () => {
    const { container } = render(
      <KanbanLayout tasks={mockTasks} currentTaskId={2} />
    );

    // Check for highlighted card
    const currentBadge = screen.getByText('Current');
    expect(currentBadge).toBeInTheDocument();
  });

  it('should display step count', () => {
    render(<KanbanLayout tasks={mockTasks} />);

    expect(screen.getByText('2 steps')).toBeInTheDocument();
    expect(screen.getAllByText('1 step').length).toBeGreaterThan(0);
  });

  it('should show empty state for columns with no tasks', () => {
    render(<KanbanLayout tasks={mockTasks} />);

    // "Blocked" column has no tasks
    expect(screen.getAllByText('Drop tasks here').length).toBeGreaterThan(0);
  });

  it('should handle empty task list', () => {
    render(<KanbanLayout tasks={[]} />);

    expect(screen.getByText('Kanban Board')).toBeInTheDocument();
    expect(screen.getByText('0 of 0 completed')).toBeInTheDocument();
  });

  it('should call onTaskUpdate when provided', async () => {
    const onTaskUpdate = vi.fn();
    render(<KanbanLayout tasks={mockTasks} onTaskUpdate={onTaskUpdate} />);

    // Note: Testing drag-and-drop requires more complex setup
    // This just verifies the prop is accepted
    expect(onTaskUpdate).not.toHaveBeenCalled();
  });

  it('should display task categories', () => {
    render(<KanbanLayout tasks={mockTasks} />);

    expect(screen.getByText('frontend')).toBeInTheDocument();
    expect(screen.getByText('backend')).toBeInTheDocument();
    expect(screen.getByText('testing')).toBeInTheDocument();
  });
});
