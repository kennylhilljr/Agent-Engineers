/**
 * MilestoneCard Component Unit Tests
 * Comprehensive test suite for MilestoneCard component
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MilestoneCard } from '@/components/a2ui-catalog/milestone-card';
import { A2UIProps, MilestoneCardData } from '@/lib/a2ui-types';

describe('MilestoneCard Component', () => {
  describe('Basic Rendering', () => {
    test('renders with minimal required props', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-001',
          title: 'Project Alpha Complete',
          summary: 'All core features implemented',
          tasksCompleted: 15,
          totalTasks: 15,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('milestone-card')).toBeInTheDocument();
      expect(screen.getByText('Project Alpha Complete')).toBeInTheDocument();
    });

    test('renders with all optional props', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-002',
          title: 'MVP Launch',
          summary: 'Successfully launched minimum viable product',
          tasksCompleted: 20,
          totalTasks: 25,
          nextPhase: 'User testing and feedback collection',
          completionDate: new Date('2024-12-15'),
          celebrationMessage: 'Amazing work team! You crushed it!',
          celebrationAnimation: true,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByText('MVP Launch')).toBeInTheDocument();
      expect(screen.getByText('Successfully launched minimum viable product')).toBeInTheDocument();
      expect(screen.getByText('User testing and feedback collection')).toBeInTheDocument();
      expect(screen.getByText('"Amazing work team! You crushed it!"')).toBeInTheDocument();
    });

    test('renders default title when title is empty', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-003',
          title: '',
          summary: 'A milestone was reached',
          tasksCompleted: 5,
          totalTasks: 5,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByText('Milestone Reached!')).toBeInTheDocument();
    });

    test('renders default summary when summary is empty', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-004',
          title: 'Test Milestone',
          summary: '',
          tasksCompleted: 3,
          totalTasks: 3,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByText('Milestone completed successfully.')).toBeInTheDocument();
    });
  });

  describe('Tasks Counter Display', () => {
    test('displays correct task completion ratio', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-005',
          title: 'Sprint 1',
          summary: 'First sprint completed',
          tasksCompleted: 8,
          totalTasks: 10,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('tasks-counter')).toBeInTheDocument();
      expect(screen.getByTestId('completion-badge')).toHaveTextContent('8 / 10');
    });

    test('displays 100% completion correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-006',
          title: 'Full Completion',
          summary: 'All tasks done',
          tasksCompleted: 20,
          totalTasks: 20,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('completion-badge')).toHaveTextContent('20 / 20');
      expect(screen.getByTestId('completion-percentage')).toHaveTextContent('100%');
    });

    test('handles zero total tasks', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-007',
          title: 'Empty Milestone',
          summary: 'No tasks',
          tasksCompleted: 0,
          totalTasks: 0,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('completion-percentage')).toHaveTextContent('0%');
    });

    test('calculates partial completion percentage correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-008',
          title: 'Partial Progress',
          summary: 'Halfway there',
          tasksCompleted: 5,
          totalTasks: 10,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('completion-percentage')).toHaveTextContent('50%');
    });

    test('rounds completion percentage correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-009',
          title: 'Complex Ratio',
          summary: 'Odd numbers',
          tasksCompleted: 7,
          totalTasks: 9,
        },
      };

      render(<MilestoneCard {...props} />);
      // 7/9 = 77.777... should round to 78%
      expect(screen.getByTestId('completion-percentage')).toHaveTextContent('78%');
    });
  });

  describe('Progress Bar', () => {
    test('displays progress bar', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-010',
          title: 'Progress Test',
          summary: 'Testing progress bar',
          tasksCompleted: 6,
          totalTasks: 10,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('progress-section')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
    });

    test('progress bar shows correct percentage in label', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-011',
          title: 'Test',
          summary: 'Test',
          tasksCompleted: 3,
          totalTasks: 4,
        },
      };

      render(<MilestoneCard {...props} />);
      // 3/4 = 75%
      expect(screen.getByTestId('completion-percentage')).toHaveTextContent('75%');
    });
  });

  describe('Celebration Message', () => {
    test('displays celebration message when provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-012',
          title: 'Big Win',
          summary: 'Major achievement',
          tasksCompleted: 100,
          totalTasks: 100,
          celebrationMessage: 'Incredible job! This is a huge milestone!',
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('celebration-message')).toBeInTheDocument();
      expect(screen.getByText('"Incredible job! This is a huge milestone!"')).toBeInTheDocument();
    });

    test('does not display celebration message when not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-013',
          title: 'No Message',
          summary: 'Simple milestone',
          tasksCompleted: 5,
          totalTasks: 5,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.queryByTestId('celebration-message')).not.toBeInTheDocument();
    });

    test('displays empty celebration message', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-014',
          title: 'Empty Message',
          summary: 'Test',
          tasksCompleted: 1,
          totalTasks: 1,
          celebrationMessage: '',
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.queryByTestId('celebration-message')).not.toBeInTheDocument();
    });
  });

  describe('Completion Date', () => {
    test('displays completion date when provided', () => {
      const testDate = new Date('2024-06-15T12:00:00Z');
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-015',
          title: 'Dated Milestone',
          summary: 'With completion date',
          tasksCompleted: 10,
          totalTasks: 10,
          completionDate: testDate,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('completion-date')).toBeInTheDocument();
      expect(screen.getByTestId('completion-date')).toHaveTextContent(/June/);
      expect(screen.getByTestId('completion-date')).toHaveTextContent(/2024/);
    });

    test('does not display completion date when not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-016',
          title: 'No Date',
          summary: 'Without date',
          tasksCompleted: 5,
          totalTasks: 5,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.queryByTestId('completion-date')).not.toBeInTheDocument();
    });

    test('formats completion date correctly', () => {
      const testDate = new Date('2024-12-25T12:00:00Z');
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-017',
          title: 'Christmas Release',
          summary: 'Holiday delivery',
          tasksCompleted: 50,
          totalTasks: 50,
          completionDate: testDate,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('completion-date')).toHaveTextContent(/December/);
      expect(screen.getByTestId('completion-date')).toHaveTextContent(/2024/);
    });
  });

  describe('Next Phase Preview', () => {
    test('displays next phase when provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-018',
          title: 'Phase 1 Complete',
          summary: 'Ready for next phase',
          tasksCompleted: 20,
          totalTasks: 20,
          nextPhase: 'Phase 2: Advanced Features',
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('next-phase')).toBeInTheDocument();
      expect(screen.getByText('Phase 2: Advanced Features')).toBeInTheDocument();
      expect(screen.getByText('Up Next')).toBeInTheDocument();
    });

    test('does not display next phase when not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-019',
          title: 'Final Milestone',
          summary: 'No more phases',
          tasksCompleted: 100,
          totalTasks: 100,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.queryByTestId('next-phase')).not.toBeInTheDocument();
    });

    test('displays empty next phase text', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-020',
          title: 'Test',
          summary: 'Test',
          tasksCompleted: 1,
          totalTasks: 1,
          nextPhase: '',
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.queryByTestId('next-phase')).not.toBeInTheDocument();
    });
  });

  describe('Celebration Animations', () => {
    test('enables animations by default', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-021',
          title: 'Animated Milestone',
          summary: 'With animations',
          tasksCompleted: 10,
          totalTasks: 10,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('glow-effect')).toBeInTheDocument();
      expect(screen.getByTestId('sparkle-1')).toBeInTheDocument();
      expect(screen.getByTestId('sparkle-2')).toBeInTheDocument();
      expect(screen.getByTestId('sparkle-3')).toBeInTheDocument();
      expect(screen.getByTestId('icon-glow')).toBeInTheDocument();
    });

    test('disables animations when celebrationAnimation is false', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-022',
          title: 'No Animation',
          summary: 'Static milestone',
          tasksCompleted: 5,
          totalTasks: 5,
          celebrationAnimation: false,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.queryByTestId('glow-effect')).not.toBeInTheDocument();
      expect(screen.queryByTestId('sparkle-1')).not.toBeInTheDocument();
      expect(screen.queryByTestId('sparkle-2')).not.toBeInTheDocument();
      expect(screen.queryByTestId('sparkle-3')).not.toBeInTheDocument();
      expect(screen.queryByTestId('icon-glow')).not.toBeInTheDocument();
    });

    test('enables animations when celebrationAnimation is true', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-023',
          title: 'Explicit Animation',
          summary: 'Animations on',
          tasksCompleted: 8,
          totalTasks: 8,
          celebrationAnimation: true,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('glow-effect')).toBeInTheDocument();
      expect(screen.getByTestId('sparkle-1')).toBeInTheDocument();
    });

    test('animation state changes after mount', async () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-024',
          title: 'Animated Test',
          summary: 'Testing animation trigger',
          tasksCompleted: 3,
          totalTasks: 3,
          celebrationAnimation: true,
        },
      };

      render(<MilestoneCard {...props} />);

      // Initially, animation classes should not be fully applied
      const glowEffect = screen.getByTestId('glow-effect');

      // Wait for animation to trigger (100ms timeout in component)
      await waitFor(() => {
        expect(glowEffect).toHaveClass('opacity-100');
      }, { timeout: 200 });
    });
  });

  describe('CheckCircle Icon', () => {
    test('displays check icon', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-025',
          title: 'Icon Test',
          summary: 'Testing icon display',
          tasksCompleted: 1,
          totalTasks: 1,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('check-icon')).toBeInTheDocument();
      expect(screen.getByTestId('check-icon-container')).toBeInTheDocument();
    });

    test('check icon has correct styling', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-026',
          title: 'Style Test',
          summary: 'Testing styles',
          tasksCompleted: 2,
          totalTasks: 2,
        },
      };

      render(<MilestoneCard {...props} />);
      const icon = screen.getByTestId('check-icon');
      expect(icon).toHaveClass('text-green-400');
    });
  });

  describe('Visual Design and Styling', () => {
    test('applies green gradient background', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-027',
          title: 'Style Test',
          summary: 'Testing background',
          tasksCompleted: 5,
          totalTasks: 5,
        },
      };

      render(<MilestoneCard {...props} />);
      const card = screen.getByTestId('milestone-card');
      expect(card).toHaveClass('bg-gradient-to-br');
    });

    test('applies dark theme text colors', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-028',
          title: 'Color Test',
          summary: 'Testing colors',
          tasksCompleted: 3,
          totalTasks: 3,
        },
      };

      render(<MilestoneCard {...props} />);
      const card = screen.getByTestId('milestone-card');
      expect(card).toHaveClass('text-gray-100');
    });

    test('has proper border styling', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-029',
          title: 'Border Test',
          summary: 'Testing borders',
          tasksCompleted: 1,
          totalTasks: 1,
        },
      };

      render(<MilestoneCard {...props} />);
      const card = screen.getByTestId('milestone-card');
      expect(card).toHaveClass('border-green-500/30');
    });
  });

  describe('Summary Text', () => {
    test('displays milestone summary', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-030',
          title: 'Summary Test',
          summary: 'This is a detailed summary of the milestone achievement',
          tasksCompleted: 7,
          totalTasks: 7,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('milestone-summary')).toBeInTheDocument();
      expect(screen.getByText('This is a detailed summary of the milestone achievement')).toBeInTheDocument();
    });
  });

  describe('Title Display', () => {
    test('displays milestone title with proper styling', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-031',
          title: 'Major Launch',
          summary: 'Product launch successful',
          tasksCompleted: 50,
          totalTasks: 50,
        },
      };

      render(<MilestoneCard {...props} />);
      const title = screen.getByTestId('milestone-title');
      expect(title).toBeInTheDocument();
      expect(title).toHaveTextContent('Major Launch');
      expect(title).toHaveClass('text-2xl');
    });
  });

  describe('Edge Cases', () => {
    test('handles tasksCompleted greater than totalTasks', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-032',
          title: 'Over Completion',
          summary: 'Extra tasks completed',
          tasksCompleted: 12,
          totalTasks: 10,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('completion-badge')).toHaveTextContent('12 / 10');
      // 12/10 = 120%
      expect(screen.getByTestId('completion-percentage')).toHaveTextContent('120%');
    });

    test('handles very large task numbers', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-033',
          title: 'Huge Project',
          summary: 'Massive undertaking',
          tasksCompleted: 9999,
          totalTasks: 10000,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('completion-badge')).toHaveTextContent('9999 / 10000');
    });

    test('handles single task milestone', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-034',
          title: 'Single Task',
          summary: 'One task milestone',
          tasksCompleted: 1,
          totalTasks: 1,
        },
      };

      render(<MilestoneCard {...props} />);
      expect(screen.getByTestId('completion-badge')).toHaveTextContent('1 / 1');
      expect(screen.getByTestId('completion-percentage')).toHaveTextContent('100%');
    });
  });

  describe('Component Type and Data', () => {
    test('accepts correct component type', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-035',
          title: 'Type Test',
          summary: 'Testing type',
          tasksCompleted: 2,
          totalTasks: 2,
        },
      };

      expect(() => render(<MilestoneCard {...props} />)).not.toThrow();
    });

    test('renders with metadata', () => {
      const props: A2UIProps = {
        type: 'a2ui.MilestoneCard',
        data: {
          milestoneId: 'ms-036',
          title: 'Metadata Test',
          summary: 'With metadata',
          tasksCompleted: 3,
          totalTasks: 3,
        },
        metadata: {
          componentId: 'test-component',
          timestamp: '2024-12-01T10:00:00Z',
          source: 'test-suite',
        },
      };

      expect(() => render(<MilestoneCard {...props} />)).not.toThrow();
    });
  });
});
