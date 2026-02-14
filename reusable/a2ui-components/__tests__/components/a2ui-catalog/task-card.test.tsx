/**
 * TaskCard Component Unit Tests
 * Comprehensive test suite for TaskCard component
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { TaskCard } from '@/components/a2ui-catalog/task-card';
import { A2UIProps, TaskCardData } from '@/lib/a2ui-types';

describe('TaskCard Component', () => {
  describe('Basic Rendering', () => {
    test('renders with minimal props', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: {
          title: 'Test Task',
          status: 'pending',
        },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Test Task')).toBeInTheDocument();
      expect(screen.getByTestId('task-card')).toBeInTheDocument();
    });

    test('renders untitled task when title is missing', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: {
          status: 'pending',
        },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Untitled Task')).toBeInTheDocument();
    });

    test('renders with all props provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: {
          title: 'Complete Task',
          status: 'in_progress',
          category: 'frontend',
          progress: 75,
          assignee: 'John Doe',
          dueDate: '2024-12-31',
          description: 'This is a test task description',
        },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Complete Task')).toBeInTheDocument();
      expect(screen.getByText('This is a test task description')).toBeInTheDocument();
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('75%')).toBeInTheDocument();
    });
  });

  describe('Status Badge Display', () => {
    test('displays pending status with correct styling', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      const badge = screen.getByTestId('status-badge');
      expect(badge).toBeInTheDocument();
      expect(screen.getByText('Pending')).toBeInTheDocument();
    });

    test('displays in_progress status with correct styling', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'in_progress' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('In Progress')).toBeInTheDocument();
      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveClass('text-blue-400');
    });

    test('displays completed status with correct styling', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'completed' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Completed')).toBeInTheDocument();
      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveClass('text-green-400');
    });

    test('displays blocked status with correct styling', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'blocked' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Blocked')).toBeInTheDocument();
      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveClass('text-red-400');
    });
  });

  describe('Category Badge Display', () => {
    test('displays setup category badge', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', category: 'setup' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Setup')).toBeInTheDocument();
      expect(screen.getByTestId('category-badge')).toBeInTheDocument();
    });

    test('displays backend category badge', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', category: 'backend' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Backend')).toBeInTheDocument();
    });

    test('displays frontend category badge', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', category: 'frontend' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Frontend')).toBeInTheDocument();
    });

    test('displays a2ui-catalog category badge', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', category: 'a2ui-catalog' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('A2UI Catalog')).toBeInTheDocument();
    });

    test('displays feature category badge', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', category: 'feature' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Feature')).toBeInTheDocument();
    });

    test('displays testing category badge', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', category: 'testing' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Testing')).toBeInTheDocument();
    });

    test('displays styling category badge', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', category: 'styling' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Styling')).toBeInTheDocument();
    });

    test('does not display category badge when category is not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      expect(screen.queryByTestId('category-badge')).not.toBeInTheDocument();
    });
  });

  describe('Progress Bar Display', () => {
    test('displays progress bar when progress is provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'in_progress', progress: 50 },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByTestId('progress-container')).toBeInTheDocument();
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    test('displays correct progress percentage (0%)', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', progress: 0 },
      };

      render(<TaskCard {...props} />);
      expect(screen.queryByTestId('progress-container')).not.toBeInTheDocument();
    });

    test('displays correct progress percentage (25%)', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'in_progress', progress: 25 },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('25%')).toBeInTheDocument();
    });

    test('displays correct progress percentage (100%)', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'completed', progress: 100 },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    test('does not display progress bar when progress is 0', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', progress: 0 },
      };

      render(<TaskCard {...props} />);
      expect(screen.queryByTestId('progress-container')).not.toBeInTheDocument();
    });

    test('does not display progress bar when progress is not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      expect(screen.queryByTestId('progress-container')).not.toBeInTheDocument();
    });
  });

  describe('Metadata Display', () => {
    test('displays assignee when provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', assignee: 'Alice Smith' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByTestId('assignee')).toBeInTheDocument();
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });

    test('displays due date when provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending', dueDate: '2024-12-25' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByTestId('due-date')).toBeInTheDocument();
      // Date format is locale-specific, just check it contains the date
      const dateElement = screen.getByTestId('due-date');
      expect(dateElement).toHaveTextContent(/2024/);
    });

    test('displays both assignee and due date', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: {
          title: 'Task',
          status: 'pending',
          assignee: 'Bob Jones',
          dueDate: '2024-11-15',
        },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Bob Jones')).toBeInTheDocument();
      const dateElement = screen.getByTestId('due-date');
      expect(dateElement).toHaveTextContent(/2024/);
    });

    test('does not display assignee when not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      expect(screen.queryByTestId('assignee')).not.toBeInTheDocument();
    });

    test('does not display due date when not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      expect(screen.queryByTestId('due-date')).not.toBeInTheDocument();
    });
  });

  describe('Description Display', () => {
    test('displays description when provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: {
          title: 'Task',
          status: 'pending',
          description: 'This is a detailed task description',
        },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByTestId('task-description')).toBeInTheDocument();
      expect(screen.getByText('This is a detailed task description')).toBeInTheDocument();
    });

    test('does not display description when not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      expect(screen.queryByTestId('task-description')).not.toBeInTheDocument();
    });
  });

  describe('Event Handling', () => {
    test('calls onEvent when card is clicked', () => {
      const mockOnEvent = jest.fn();
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
        onEvent: mockOnEvent,
      };

      render(<TaskCard {...props} />);
      const card = screen.getByTestId('task-card');
      fireEvent.click(card);

      expect(mockOnEvent).toHaveBeenCalledTimes(1);
      expect(mockOnEvent).toHaveBeenCalledWith(
        'click',
        expect.objectContaining({
          action: 'view_details',
        })
      );
    });

    test('does not throw error when onEvent is not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      const card = screen.getByTestId('task-card');

      expect(() => {
        fireEvent.click(card);
      }).not.toThrow();
    });
  });

  describe('Responsive Design & Styling', () => {
    test('applies dark theme classes', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      const card = screen.getByTestId('task-card');
      expect(card).toHaveClass('bg-gray-900', 'border-gray-800', 'text-gray-100');
    });

    test('applies hover effect classes', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      const card = screen.getByTestId('task-card');
      expect(card).toHaveClass('hover:border-blue-500/50', 'transition-all');
    });
  });
});
