/**
 * ProgressRing Component Unit Tests
 * Comprehensive test suite for ProgressRing component
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { ProgressRing } from '@/components/a2ui-catalog/progress-ring';
import { A2UIProps, ProgressRingData } from '@/lib/a2ui-types';

describe('ProgressRing Component', () => {
  describe('Basic Rendering', () => {
    test('renders with minimal props (0%)', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 0,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('progress-ring-container')).toBeInTheDocument();
      expect(screen.getByTestId('progress-ring')).toBeInTheDocument();
      expect(screen.getByTestId('percentage-display')).toBeInTheDocument();
    });

    test('renders percentage value in center', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 50,
        },
      };

      render(<ProgressRing {...props} />);
      const percentageDisplay = screen.getByTestId('percentage-display');
      expect(percentageDisplay).toHaveTextContent('50');
      expect(percentageDisplay).toHaveTextContent('%');
    });

    test('renders SVG elements', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 25,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('progress-svg')).toBeInTheDocument();
      expect(screen.getByTestId('background-circle')).toBeInTheDocument();
      expect(screen.getByTestId('progress-circle')).toBeInTheDocument();
    });

    test('renders metrics container', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 50,
          tasksCompleted: 5,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('metrics-container')).toBeInTheDocument();
    });
  });

  describe('Percentage Display', () => {
    test('displays 0% correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 0 },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('percentage-display')).toHaveTextContent('0');
    });

    test('displays 25% correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 25 },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('percentage-display')).toHaveTextContent('25');
    });

    test('displays 50% correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 50 },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('percentage-display')).toHaveTextContent('50');
    });

    test('displays 75% correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 75 },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('percentage-display')).toHaveTextContent('75');
    });

    test('displays 100% correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 100 },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('percentage-display')).toHaveTextContent('100');
    });

    test('clamps percentage above 100 to 100', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 150 },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('percentage-display')).toHaveTextContent('100');
    });

    test('clamps negative percentage to 0', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: -10 },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('percentage-display')).toHaveTextContent('0');
    });
  });

  describe('Color Coding by Threshold', () => {
    test('applies red color for 0%', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 0 },
      };

      render(<ProgressRing {...props} />);
      const circle = screen.getByTestId('progress-circle');
      expect(circle).toHaveClass('stroke-red-500');
    });

    test('applies red color for 49% (below 50)', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 49 },
      };

      render(<ProgressRing {...props} />);
      const circle = screen.getByTestId('progress-circle');
      expect(circle).toHaveClass('stroke-red-500');
    });

    test('applies orange color for 50%', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 50 },
      };

      render(<ProgressRing {...props} />);
      const circle = screen.getByTestId('progress-circle');
      expect(circle).toHaveClass('stroke-orange-500');
    });

    test('applies orange color for 79% (below 80)', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 79 },
      };

      render(<ProgressRing {...props} />);
      const circle = screen.getByTestId('progress-circle');
      expect(circle).toHaveClass('stroke-orange-500');
    });

    test('applies green color for 80%', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 80 },
      };

      render(<ProgressRing {...props} />);
      const circle = screen.getByTestId('progress-circle');
      expect(circle).toHaveClass('stroke-green-500');
    });

    test('applies green color for 100%', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 100 },
      };

      render(<ProgressRing {...props} />);
      const circle = screen.getByTestId('progress-circle');
      expect(circle).toHaveClass('stroke-green-500');
    });
  });

  describe('Metrics Display', () => {
    test('displays tasks completed metric', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 50,
          tasksCompleted: 5,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('tasks-completed')).toBeInTheDocument();
      expect(screen.getByText('Tasks Completed')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    test('displays files modified metric', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 50,
          filesModified: 12,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('files-modified')).toBeInTheDocument();
      expect(screen.getByText('Files Modified')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();
    });

    test('displays tests completed metric', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 50,
          testsCompleted: 25,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('tests-completed')).toBeInTheDocument();
      expect(screen.getByText('Tests Completed')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
    });

    test('displays all metrics when all provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 75,
          tasksCompleted: 8,
          filesModified: 15,
          testsCompleted: 30,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('tasks-completed')).toBeInTheDocument();
      expect(screen.getByTestId('files-modified')).toBeInTheDocument();
      expect(screen.getByTestId('tests-completed')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
      expect(screen.getByText('15')).toBeInTheDocument();
      expect(screen.getByText('30')).toBeInTheDocument();
    });

    test('does not display metrics when not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 50,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.queryByTestId('tasks-completed')).not.toBeInTheDocument();
      expect(screen.queryByTestId('files-modified')).not.toBeInTheDocument();
      expect(screen.queryByTestId('tests-completed')).not.toBeInTheDocument();
    });

    test('handles zero values for metrics', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 0,
          tasksCompleted: 0,
          filesModified: 0,
          testsCompleted: 0,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('tasks-completed')).toBeInTheDocument();
      expect(screen.getByTestId('files-modified')).toBeInTheDocument();
      expect(screen.getByTestId('tests-completed')).toBeInTheDocument();
      // Should display '0' three times for each metric
      const zeros = screen.getAllByText('0');
      // At least 3 zeros should exist (one for each metric value)
      expect(zeros.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('Optional Label', () => {
    test('displays label when provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 75,
          label: 'Project Progress',
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.getByTestId('progress-label')).toBeInTheDocument();
      expect(screen.getByText('Project Progress')).toBeInTheDocument();
    });

    test('does not display label when not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 50,
        },
      };

      render(<ProgressRing {...props} />);
      expect(screen.queryByTestId('progress-label')).not.toBeInTheDocument();
    });
  });

  describe('SVG Animation & Transitions', () => {
    test('applies transition classes to progress circle', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 60 },
      };

      render(<ProgressRing {...props} />);
      const circle = screen.getByTestId('progress-circle');
      expect(circle).toHaveClass('transition-all');
      expect(circle).toHaveClass('duration-1000');
      expect(circle).toHaveClass('ease-out');
    });

    test('applies transition classes to SVG container', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 60 },
      };

      render(<ProgressRing {...props} />);
      const svg = screen.getByTestId('progress-svg');
      expect(svg).toHaveClass('transition-all');
      expect(svg).toHaveClass('duration-500');
    });

    test('applies rotation transform to SVG', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 50 },
      };

      render(<ProgressRing {...props} />);
      const svg = screen.getByTestId('progress-svg');
      expect(svg).toHaveClass('-rotate-90');
    });
  });

  describe('Dark Theme Styling', () => {
    test('applies dark theme background to container', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 50 },
      };

      render(<ProgressRing {...props} />);
      const container = screen.getByTestId('progress-ring-container');
      expect(container).toHaveClass('bg-gray-900');
      expect(container).toHaveClass('border-gray-800');
    });

    test('applies dark theme to background circle', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 50 },
      };

      render(<ProgressRing {...props} />);
      const bgCircle = screen.getByTestId('background-circle');
      expect(bgCircle).toHaveClass('text-gray-800');
    });

    test('applies dark theme to percentage display', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 50 },
      };

      const { container } = render(<ProgressRing {...props} />);
      const percentageElement = container.querySelector('.text-2xl.text-gray-400');
      expect(percentageElement).toBeInTheDocument();
    });
  });

  describe('Responsive Design', () => {
    test('container has proper padding and layout classes', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: { percentage: 50 },
      };

      render(<ProgressRing {...props} />);
      const container = screen.getByTestId('progress-ring-container');
      expect(container).toHaveClass('flex');
      expect(container).toHaveClass('flex-col');
      expect(container).toHaveClass('items-center');
      expect(container).toHaveClass('justify-center');
      expect(container).toHaveClass('p-6');
    });

    test('metrics container uses full width', () => {
      const props: A2UIProps = {
        type: 'a2ui.ProgressRing',
        data: {
          percentage: 50,
          tasksCompleted: 5,
        },
      };

      render(<ProgressRing {...props} />);
      const metricsContainer = screen.getByTestId('metrics-container');
      expect(metricsContainer).toHaveClass('w-full');
    });
  });
});
