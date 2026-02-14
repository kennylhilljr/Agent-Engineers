/**
 * A2UI Component Rendering Tests
 * Tests for individual component implementations
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { TaskCard } from '@/components/a2ui-catalog/task-card';
import { ProgressRing } from '@/components/a2ui-catalog/progress-ring';
import { FileTree } from '@/components/a2ui-catalog/file-tree';
import { TestResults } from '@/components/a2ui-catalog/test-results';
import { ActivityItem } from '@/components/a2ui-catalog/activity-item';
import { ApprovalCard } from '@/components/a2ui-catalog/approval-card';
import { DecisionCard } from '@/components/a2ui-catalog/decision-card';
import { MilestoneCard } from '@/components/a2ui-catalog/milestone-card';
import { ErrorCard } from '@/components/a2ui-catalog/error-card';
import { A2UIProps } from '@/lib/a2ui-types';

describe('A2UI Component Rendering', () => {
  describe('TaskCard', () => {
    test('renders with basic props', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: {
          title: 'Test Task',
          status: 'pending',
        },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Test Task')).toBeInTheDocument();
    });

    test('displays task title', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Test', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Test')).toBeInTheDocument();
    });

    test('displays status badge', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Task', status: 'pending' },
      };

      render(<TaskCard {...props} />);
      expect(screen.getByText('Pending')).toBeInTheDocument();
    });
  });

  describe('ProgressRing', () => {
    test('renders with basic props', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 75,
          label: 'Progress',
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByText(/a2ui.ProgressRing/i)).toBeInTheDocument();
    });
  });

  describe('FileTree', () => {
    test('renders with basic props', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            { path: '/src', name: 'src', type: 'directory' as const },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText(/a2ui.FileTree/i)).toBeInTheDocument();
    });
  });

  describe('TestResults', () => {
    test('renders with basic props', () => {
      const props: A2UIProps = {
        type: 'a2ui.TestResults',
        data: {
          totalTests: 10,
          passedTests: 8,
          failedTests: 2,
        },
      };

      render(<TestResults {...props} />);
      expect(screen.getByText(/a2ui.TestResults/i)).toBeInTheDocument();
    });
  });

  describe('ActivityItem', () => {
    test('renders with basic props', () => {
      const props: A2UIProps = {
        type: 'a2ui.ActivityItem',
        data: {
          actor: 'John Doe',
          action: 'created',
          timestamp: '2024-01-01T00:00:00Z',
        },
      };

      render(<ActivityItem {...props} />);
      expect(screen.getByText(/a2ui.ActivityItem/i)).toBeInTheDocument();
    });
  });

  describe('ApprovalCard', () => {
    test('renders with basic props', () => {
      const props: A2UIProps = {
        type: 'a2ui.ApprovalCard',
        data: {
          title: 'Approval Request',
          description: 'Please approve',
          requester: 'Jane Doe',
          requestedAt: '2024-01-01T00:00:00Z',
        },
      };

      render(<ApprovalCard {...props} />);
      expect(screen.getByText(/a2ui.ApprovalCard/i)).toBeInTheDocument();
    });
  });

  describe('DecisionCard', () => {
    test('renders with basic props', () => {
      const props: A2UIProps = {
        type: 'a2ui.DecisionCard',
        data: {
          decisionId: 'dec-1',
          question: 'Choose an option',
          options: [
            { id: '1', label: 'Option 1' },
            { id: '2', label: 'Option 2' },
          ],
        },
      };

      render(<DecisionCard {...props} />);
      expect(screen.getByText('Choose an option')).toBeInTheDocument();
      expect(screen.getByTestId('decision-card')).toBeInTheDocument();
    });
  });

  describe('MilestoneCard', () => {
    test('renders with basic props', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          title: 'Milestone 1',
          status: 'in-progress' as const,
          dueDate: '2024-12-31',
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByText(/a2ui.MilestoneCard/i)).toBeInTheDocument();
    });
  });

  describe('ErrorCard', () => {
    test('renders with basic props', () => {
      const props: A2UIProps = {
        type: 'a2ui.ErrorCard',
        data: {
          message: 'An error occurred',
          code: 'ERR_001',
        },
      };

      render(<ErrorCard {...props} />);
      expect(screen.getByText(/a2ui.ErrorCard/i)).toBeInTheDocument();
    });
  });
});

describe('Component Props Handling', () => {
  test('components handle empty data objects', () => {
    const props: A2UIProps = {
      type: 'a2ui.TaskCard',
      data: {},
    };

    const { container } = render(<TaskCard {...props} />);
    expect(container).toBeInTheDocument();
  });

  test('components handle metadata', () => {
    const props: A2UIProps = {
      type: 'a2ui.TaskCard',
      data: { title: 'Test' },
      metadata: {
        componentId: 'task-123',
        timestamp: '2024-01-01T00:00:00Z',
      },
    };

    const { container } = render(<TaskCard {...props} />);
    expect(container).toBeInTheDocument();
  });

  test('components handle onEvent callback', () => {
    const mockOnEvent = jest.fn();
    const props: A2UIProps = {
      type: 'a2ui.ApprovalCard',
      data: {
        title: 'Test',
        description: 'Test',
        requester: 'Test',
        requestedAt: '2024-01-01',
      },
      onEvent: mockOnEvent,
    };

    const { container } = render(<ApprovalCard {...props} />);
    expect(container).toBeInTheDocument();
    // Note: Event handling will be tested when components are fully implemented
  });
});
