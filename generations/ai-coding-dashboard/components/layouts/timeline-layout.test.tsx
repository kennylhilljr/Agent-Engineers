/**
 * Unit Tests for Timeline Layout Component
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TimelineLayout } from './timeline-layout';
import { Task } from '@/db/schema';

describe('TimelineLayout', () => {
  const mockTasks: Task[] = [
    {
      id: 1,
      projectId: 1,
      category: 'frontend',
      description: 'Build homepage',
      steps: ['Create component', 'Add styles', 'Test'],
      status: 'done',
      agentNotes: null,
      order: 0,
    },
    {
      id: 2,
      projectId: 1,
      category: 'backend',
      description: 'Create API endpoint',
      steps: ['Define schema', 'Implement handler'],
      status: 'in_progress',
      agentNotes: 'Working on authentication',
      order: 1,
    },
    {
      id: 3,
      projectId: 1,
      category: 'testing',
      description: 'Write unit tests',
      steps: ['Test frontend', 'Test backend'],
      status: 'todo',
      agentNotes: null,
      order: 2,
    },
  ];

  it('should render timeline header', () => {
    render(<TimelineLayout tasks={mockTasks} />);

    expect(screen.getByText('Project Timeline')).toBeInTheDocument();
    expect(screen.getByText(/Sequential task workflow/i)).toBeInTheDocument();
  });

  it('should render all tasks in order', () => {
    render(<TimelineLayout tasks={mockTasks} />);

    expect(screen.getByText('Build homepage')).toBeInTheDocument();
    expect(screen.getByText('Create API endpoint')).toBeInTheDocument();
    expect(screen.getByText('Write unit tests')).toBeInTheDocument();
  });

  it('should display task categories', () => {
    render(<TimelineLayout tasks={mockTasks} />);

    expect(screen.getByText('frontend')).toBeInTheDocument();
    expect(screen.getByText('backend')).toBeInTheDocument();
    expect(screen.getByText('testing')).toBeInTheDocument();
  });

  it('should display task steps', () => {
    render(<TimelineLayout tasks={mockTasks} />);

    expect(screen.getByText('Create component')).toBeInTheDocument();
    expect(screen.getByText('Add styles')).toBeInTheDocument();
    expect(screen.getByText('Define schema')).toBeInTheDocument();
  });

  it('should display agent notes when present', () => {
    render(<TimelineLayout tasks={mockTasks} />);

    expect(screen.getByText('Working on authentication')).toBeInTheDocument();
  });

  it('should highlight current task', () => {
    const { container } = render(
      <TimelineLayout tasks={mockTasks} currentTaskId={2} />
    );

    const currentCard = container.querySelector('.ring-blue-500');
    expect(currentCard).toBeInTheDocument();
  });

  it('should display progress bar', () => {
    render(<TimelineLayout tasks={mockTasks} />);

    expect(screen.getByText('1 of 3 completed')).toBeInTheDocument();
    expect(screen.getByText('33%')).toBeInTheDocument();
  });

  it('should display status summary', () => {
    render(<TimelineLayout tasks={mockTasks} />);

    // Use getAllByText because these labels appear multiple times
    expect(screen.getAllByText('To Do').length).toBeGreaterThan(0);
    expect(screen.getAllByText('In Progress').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Done').length).toBeGreaterThan(0);
  });

  it('should handle empty task list', () => {
    render(<TimelineLayout tasks={[]} />);

    expect(screen.getByText('Project Timeline')).toBeInTheDocument();
    expect(screen.getByText('0 of 0 completed')).toBeInTheDocument();
  });

  it('should render tasks in correct order', () => {
    const { container } = render(<TimelineLayout tasks={mockTasks} />);

    const taskDescriptions = Array.from(
      container.querySelectorAll('.text-lg.font-semibold')
    ).map(el => el.textContent);

    expect(taskDescriptions).toEqual([
      'Build homepage',
      'Create API endpoint',
      'Write unit tests',
    ]);
  });

  it('should display task numbers', () => {
    render(<TimelineLayout tasks={mockTasks} />);

    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();
    expect(screen.getByText('#3')).toBeInTheDocument();
  });
});
