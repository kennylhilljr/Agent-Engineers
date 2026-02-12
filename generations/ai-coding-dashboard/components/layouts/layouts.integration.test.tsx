/**
 * Integration Tests for Layout Components
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KanbanLayout } from './kanban-layout';
import { TimelineLayout } from './timeline-layout';
import { GraphLayout } from './graph-layout';
import { Task } from '@/db/schema';

describe('Layout Components Integration', () => {
  const mockTasks: Task[] = [
    {
      id: 1,
      projectId: 1,
      category: 'frontend',
      description: 'Build homepage',
      steps: ['Create component', 'Add styles', 'Test'],
      status: 'todo',
      agentNotes: null,
      order: 0,
    },
    {
      id: 2,
      projectId: 1,
      category: 'backend',
      description: 'Create API',
      steps: ['Define schema', 'Implement handler'],
      status: 'in_progress',
      agentNotes: 'Working on auth',
      order: 1,
    },
    {
      id: 3,
      projectId: 1,
      category: 'testing',
      description: 'Write tests',
      steps: ['Test frontend', 'Test backend'],
      status: 'done',
      agentNotes: null,
      order: 2,
    },
  ];

  describe('Layout Switching', () => {
    it('should render kanban layout with tasks', () => {
      const { container } = render(<KanbanLayout tasks={mockTasks} />);

      expect(screen.getByText('Kanban Board')).toBeInTheDocument();
      expect(screen.getByText('Build homepage')).toBeInTheDocument();
      expect(screen.getByText('Create API')).toBeInTheDocument();
      expect(screen.getByText('Write tests')).toBeInTheDocument();
    });

    it('should render timeline layout with tasks', () => {
      const { container } = render(<TimelineLayout tasks={mockTasks} />);

      expect(screen.getByText('Project Timeline')).toBeInTheDocument();
      expect(screen.getByText('Build homepage')).toBeInTheDocument();
      expect(screen.getByText('Create API')).toBeInTheDocument();
      expect(screen.getByText('Write tests')).toBeInTheDocument();
    });

    it('should render graph layout with tasks', () => {
      const { container } = render(<GraphLayout tasks={mockTasks} dependencies={[]} />);

      expect(screen.getByText('Dependency Graph')).toBeInTheDocument();
    });
  });

  describe('Data Consistency', () => {
    it('all layouts should show the same number of tasks', () => {
      const kanban = render(<KanbanLayout tasks={mockTasks} />);
      const kanbanText = kanban.container.textContent || '';

      kanban.unmount();

      const timeline = render(<TimelineLayout tasks={mockTasks} />);
      const timelineText = timeline.container.textContent || '';

      // Both should contain all task descriptions
      ['Build homepage', 'Create API', 'Write tests'].forEach(desc => {
        expect(kanbanText).toContain(desc);
        expect(timelineText).toContain(desc);
      });
    });

    it('all layouts should display task metadata consistently', () => {
      const kanban = render(<KanbanLayout tasks={mockTasks} />);
      expect(kanban.container.textContent).toContain('frontend');
      expect(kanban.container.textContent).toContain('backend');
      kanban.unmount();

      const timeline = render(<TimelineLayout tasks={mockTasks} />);
      expect(timeline.container.textContent).toContain('frontend');
      expect(timeline.container.textContent).toContain('backend');
    });
  });

  describe('Progress Tracking', () => {
    it('kanban should calculate progress correctly', () => {
      render(<KanbanLayout tasks={mockTasks} />);

      // 1 done out of 3 = 33%
      expect(screen.getByText('1 of 3 completed')).toBeInTheDocument();
      expect(screen.getByText('33%')).toBeInTheDocument();
    });

    it('timeline should calculate progress correctly', () => {
      render(<TimelineLayout tasks={mockTasks} />);

      // 1 done out of 3 = 33%
      expect(screen.getByText('1 of 3 completed')).toBeInTheDocument();
      expect(screen.getByText('33%')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty task list in all layouts', () => {
      const kanban = render(<KanbanLayout tasks={[]} />);
      expect(screen.getByText('Kanban Board')).toBeInTheDocument();
      expect(screen.getByText('0 of 0 completed')).toBeInTheDocument();
      kanban.unmount();

      const timeline = render(<TimelineLayout tasks={[]} />);
      expect(screen.getByText('Project Timeline')).toBeInTheDocument();
      expect(screen.getByText('0 of 0 completed')).toBeInTheDocument();
      timeline.unmount();

      const graph = render(<GraphLayout tasks={[]} dependencies={[]} />);
      expect(screen.getByText('Dependency Graph')).toBeInTheDocument();
    });

    it('should handle single task in all layouts', () => {
      const singleTask = [mockTasks[0]];

      const kanban = render(<KanbanLayout tasks={singleTask} />);
      expect(screen.getByText('Build homepage')).toBeInTheDocument();
      kanban.unmount();

      const timeline = render(<TimelineLayout tasks={singleTask} />);
      expect(screen.getByText('Build homepage')).toBeInTheDocument();
    });

    it('should handle tasks with no steps', () => {
      const taskWithoutSteps: Task[] = [{
        id: 99,
        projectId: 1,
        category: 'misc',
        description: 'Task without steps',
        steps: [],
        status: 'todo',
        agentNotes: null,
        order: 0,
      }];

      const kanban = render(<KanbanLayout tasks={taskWithoutSteps} />);
      expect(screen.getByText('Task without steps')).toBeInTheDocument();
      kanban.unmount();

      const timeline = render(<TimelineLayout tasks={taskWithoutSteps} />);
      expect(screen.getByText('Task without steps')).toBeInTheDocument();
    });
  });
});
