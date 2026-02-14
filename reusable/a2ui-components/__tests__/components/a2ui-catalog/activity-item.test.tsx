/**
 * ActivityItem Component Unit Tests
 * Comprehensive test suite covering all event types, statuses, and functionality
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ActivityItem, ActivityItemProps } from '@/components/a2ui-catalog/activity-item';
import { A2UIProps } from '@/lib/a2ui-types';

describe('ActivityItem Component', () => {
  const baseTimestamp = new Date('2024-02-13T10:00:00Z');

  const createProps = (overrides: Partial<ActivityItemProps> = {}): A2UIProps => ({
    type: 'a2ui.ActivityItem',
    data: {
      id: 'test-activity-1',
      type: 'task_started',
      title: 'Test Activity',
      timestamp: baseTimestamp,
      ...overrides,
    },
  });

  describe('Event Type Rendering', () => {
    test('renders task_started event type', () => {
      const props = createProps({ type: 'task_started', title: 'Started new task' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-item')).toBeInTheDocument();
      expect(screen.getByTestId('activity-title')).toHaveTextContent('Started new task');
      expect(screen.getByTestId('event-type-badge')).toHaveTextContent('Task Started');
      expect(screen.getByTestId('activity-dot')).toHaveClass('bg-blue-500');
    });

    test('renders task_completed event type', () => {
      const props = createProps({ type: 'task_completed', title: 'Completed deployment' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('event-type-badge')).toHaveTextContent('Task Completed');
      expect(screen.getByTestId('activity-dot')).toHaveClass('bg-green-500');
    });

    test('renders file_modified event type', () => {
      const props = createProps({ type: 'file_modified', title: 'Updated config.ts' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('event-type-badge')).toHaveTextContent('File Modified');
      expect(screen.getByTestId('activity-dot')).toHaveClass('bg-purple-500');
    });

    test('renders command_executed event type', () => {
      const props = createProps({ type: 'command_executed', title: 'Ran npm install' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('event-type-badge')).toHaveTextContent('Command Executed');
      expect(screen.getByTestId('activity-dot')).toHaveClass('bg-orange-500');
    });

    test('renders test_run event type', () => {
      const props = createProps({ type: 'test_run', title: 'Executed test suite' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('event-type-badge')).toHaveTextContent('Test Run');
      expect(screen.getByTestId('activity-dot')).toHaveClass('bg-indigo-500');
    });

    test('renders decision_made event type', () => {
      const props = createProps({ type: 'decision_made', title: 'Chose React framework' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('event-type-badge')).toHaveTextContent('Decision Made');
      expect(screen.getByTestId('activity-dot')).toHaveClass('bg-yellow-500');
    });

    test('renders error_occurred event type', () => {
      const props = createProps({ type: 'error_occurred', title: 'Build failed' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('event-type-badge')).toHaveTextContent('Error Occurred');
      expect(screen.getByTestId('activity-dot')).toHaveClass('bg-red-500');
    });

    test('renders milestone_reached event type', () => {
      const props = createProps({ type: 'milestone_reached', title: 'Reached 100 commits' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('event-type-badge')).toHaveTextContent('Milestone Reached');
      expect(screen.getByTestId('activity-dot')).toHaveClass('bg-emerald-500');
    });
  });

  describe('Status States', () => {
    test('renders pending status', () => {
      const props = createProps({ status: 'pending' });
      render(<ActivityItem {...props} />);

      const statusBadge = screen.getByTestId('status-badge');
      expect(statusBadge).toBeInTheDocument();
      expect(statusBadge).toHaveTextContent('Pending');
      expect(statusBadge).toHaveClass('text-gray-400');
    });

    test('renders in_progress status with spinning icon', () => {
      const props = createProps({ status: 'in_progress' });
      render(<ActivityItem {...props} />);

      const statusBadge = screen.getByTestId('status-badge');
      expect(statusBadge).toHaveTextContent('In Progress');
      expect(statusBadge).toHaveClass('text-blue-400');
    });

    test('renders completed status', () => {
      const props = createProps({ status: 'completed' });
      render(<ActivityItem {...props} />);

      const statusBadge = screen.getByTestId('status-badge');
      expect(statusBadge).toHaveTextContent('Completed');
      expect(statusBadge).toHaveClass('text-green-400');
    });

    test('renders failed status', () => {
      const props = createProps({ status: 'failed' });
      render(<ActivityItem {...props} />);

      const statusBadge = screen.getByTestId('status-badge');
      expect(statusBadge).toHaveTextContent('Failed');
      expect(statusBadge).toHaveClass('text-red-400');
    });

    test('does not render status badge when status is not provided', () => {
      const props = createProps({});
      render(<ActivityItem {...props} />);

      expect(screen.queryByTestId('status-badge')).not.toBeInTheDocument();
    });
  });

  describe('Timestamp Formatting', () => {
    beforeEach(() => {
      jest.useFakeTimers();
      jest.setSystemTime(new Date('2024-02-13T12:00:00Z'));
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    test('displays "just now" for recent timestamps', () => {
      const props = createProps({ timestamp: new Date('2024-02-13T11:59:30Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('just now');
    });

    test('displays "1 minute ago" for singular minute', () => {
      const props = createProps({ timestamp: new Date('2024-02-13T11:59:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('1 minute ago');
    });

    test('displays "X minutes ago" for multiple minutes', () => {
      const props = createProps({ timestamp: new Date('2024-02-13T11:45:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('15 minutes ago');
    });

    test('displays "1 hour ago" for singular hour', () => {
      const props = createProps({ timestamp: new Date('2024-02-13T11:00:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('1 hour ago');
    });

    test('displays "X hours ago" for multiple hours', () => {
      const props = createProps({ timestamp: new Date('2024-02-13T09:00:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('3 hours ago');
    });

    test('displays "yesterday" for 1 day ago', () => {
      const props = createProps({ timestamp: new Date('2024-02-12T12:00:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('yesterday');
    });

    test('displays "X days ago" for multiple days', () => {
      const props = createProps({ timestamp: new Date('2024-02-10T12:00:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('3 days ago');
    });

    test('displays "X weeks ago" for weeks', () => {
      const props = createProps({ timestamp: new Date('2024-01-30T12:00:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('2 weeks ago');
    });

    test('displays "X months ago" for months', () => {
      const props = createProps({ timestamp: new Date('2023-11-13T12:00:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('3 months ago');
    });

    test('displays "1 year ago" for singular year', () => {
      const props = createProps({ timestamp: new Date('2023-02-13T12:00:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('1 year ago');
    });

    test('displays "X years ago" for multiple years', () => {
      const props = createProps({ timestamp: new Date('2021-02-13T12:00:00Z') });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-timestamp')).toHaveTextContent('3 years ago');
    });
  });

  describe('Optional Props', () => {
    test('renders description when provided', () => {
      const props = createProps({ description: 'This is a detailed description' });
      render(<ActivityItem {...props} />);

      const description = screen.getByTestId('activity-description');
      expect(description).toBeInTheDocument();
      expect(description).toHaveTextContent('This is a detailed description');
    });

    test('does not render description when not provided', () => {
      const props = createProps({});
      render(<ActivityItem {...props} />);

      expect(screen.queryByTestId('activity-description')).not.toBeInTheDocument();
    });

    test('renders author when provided', () => {
      const props = createProps({ author: 'Claude AI' });
      render(<ActivityItem {...props} />);

      const author = screen.getByTestId('activity-author');
      expect(author).toBeInTheDocument();
      expect(author).toHaveTextContent('by Claude AI');
    });

    test('does not render author when not provided', () => {
      const props = createProps({});
      render(<ActivityItem {...props} />);

      expect(screen.queryByTestId('activity-author')).not.toBeInTheDocument();
    });
  });

  describe('Expandable Metadata', () => {
    test('shows expand button when metadata is provided', () => {
      const props = createProps({
        metadata: { file: 'config.ts', lines: 42 },
      });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('expand-button')).toBeInTheDocument();
      expect(screen.getByText('Show details')).toBeInTheDocument();
    });

    test('does not show expand button when metadata is not provided', () => {
      const props = createProps({});
      render(<ActivityItem {...props} />);

      expect(screen.queryByTestId('expand-button')).not.toBeInTheDocument();
    });

    test('expands metadata section when expand button is clicked', () => {
      const props = createProps({
        metadata: { file: 'config.ts', lines: 42 },
      });
      render(<ActivityItem {...props} />);

      expect(screen.queryByTestId('metadata-section')).not.toBeInTheDocument();

      fireEvent.click(screen.getByTestId('expand-button'));

      expect(screen.getByTestId('metadata-section')).toBeInTheDocument();
      expect(screen.getByText('Hide details')).toBeInTheDocument();
    });

    test('collapses metadata section when clicking expand button again', () => {
      const props = createProps({
        metadata: { file: 'config.ts' },
      });
      render(<ActivityItem {...props} />);

      const button = screen.getByTestId('expand-button');
      fireEvent.click(button);
      expect(screen.getByTestId('metadata-section')).toBeInTheDocument();

      fireEvent.click(button);
      expect(screen.queryByTestId('metadata-section')).not.toBeInTheDocument();
    });

    test('displays metadata key-value pairs', () => {
      const props = createProps({
        metadata: { file: 'config.ts', lines: 42, changes: 15 },
      });
      render(<ActivityItem {...props} />);

      fireEvent.click(screen.getByTestId('expand-button'));

      const metadataSection = screen.getByTestId('metadata-section');
      expect(metadataSection).toHaveTextContent('file:');
      expect(metadataSection).toHaveTextContent('config.ts');
      expect(metadataSection).toHaveTextContent('lines:');
      expect(metadataSection).toHaveTextContent('42');
      expect(metadataSection).toHaveTextContent('changes:');
      expect(metadataSection).toHaveTextContent('15');
    });

    test('handles object values in metadata', () => {
      const props = createProps({
        metadata: { details: { nested: 'value', count: 5 } },
      });
      render(<ActivityItem {...props} />);

      fireEvent.click(screen.getByTestId('expand-button'));

      const metadataSection = screen.getByTestId('metadata-section');
      expect(metadataSection).toHaveTextContent('details:');
      expect(metadataSection).toHaveTextContent(JSON.stringify({ nested: 'value', count: 5 }));
    });

    test('initially expanded when expanded prop is true', () => {
      const props = createProps({
        metadata: { file: 'test.ts' },
        expanded: true,
      });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('metadata-section')).toBeInTheDocument();
      expect(screen.getByText('Hide details')).toBeInTheDocument();
    });

    test('calls onExpand callback when expanding', () => {
      const onExpand = jest.fn();
      const props = createProps({
        metadata: { file: 'test.ts' },
        onExpand,
      });
      render(<ActivityItem {...props} />);

      fireEvent.click(screen.getByTestId('expand-button'));

      expect(onExpand).toHaveBeenCalledWith(true);
    });

    test('calls onExpand callback when collapsing', () => {
      const onExpand = jest.fn();
      const props = createProps({
        metadata: { file: 'test.ts' },
        expanded: true,
        onExpand,
      });
      render(<ActivityItem {...props} />);

      fireEvent.click(screen.getByTestId('expand-button'));

      expect(onExpand).toHaveBeenCalledWith(false);
    });
  });

  describe('Timeline Visual Elements', () => {
    test('renders timeline dot', () => {
      const props = createProps({});
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-dot')).toBeInTheDocument();
    });

    test('renders timeline connecting line', () => {
      const props = createProps({});
      render(<ActivityItem {...props} />);

      const line = screen.getByTestId('timeline-line');
      expect(line).toBeInTheDocument();
      expect(line).toHaveAttribute('aria-hidden', 'true');
    });

    test('renders event icon', () => {
      const props = createProps({});
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-icon')).toBeInTheDocument();
    });
  });

  describe('Data Attributes', () => {
    test('sets data-event-type attribute', () => {
      const props = createProps({ type: 'file_modified' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-item')).toHaveAttribute('data-event-type', 'file_modified');
    });

    test('sets data-status attribute when status is provided', () => {
      const props = createProps({ status: 'completed' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-item')).toHaveAttribute('data-status', 'completed');
    });

    test('timestamp has proper dateTime attribute', () => {
      const timestamp = new Date('2024-02-13T10:00:00Z');
      const props = createProps({ timestamp });
      render(<ActivityItem {...props} />);

      const timeElement = screen.getByTestId('activity-timestamp');
      expect(timeElement).toHaveAttribute('dateTime', timestamp.toISOString());
    });

    test('timestamp has title attribute with formatted date', () => {
      const timestamp = new Date('2024-02-13T10:00:00Z');
      const props = createProps({ timestamp });
      render(<ActivityItem {...props} />);

      const timeElement = screen.getByTestId('activity-timestamp');
      expect(timeElement).toHaveAttribute('title');
      expect(timeElement.getAttribute('title')).toBeTruthy();
    });
  });

  describe('Accessibility', () => {
    test('expand button has aria-expanded attribute', () => {
      const props = createProps({ metadata: { test: 'value' } });
      render(<ActivityItem {...props} />);

      const button = screen.getByTestId('expand-button');
      expect(button).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('Custom className', () => {
    test('applies custom className', () => {
      const props = createProps({ className: 'custom-class' });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-item')).toHaveClass('custom-class');
    });
  });

  describe('Edge Cases', () => {
    test('handles empty metadata object', () => {
      const props = createProps({ metadata: {} });
      render(<ActivityItem {...props} />);

      expect(screen.queryByTestId('expand-button')).not.toBeInTheDocument();
    });

    test('handles very long title', () => {
      const longTitle = 'This is a very long title that should wrap properly and not break the layout of the component';
      const props = createProps({ title: longTitle });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-title')).toHaveTextContent(longTitle);
    });

    test('handles very long description', () => {
      const longDescription = 'This is a very long description that should wrap properly and display all the content without breaking the layout or causing overflow issues';
      const props = createProps({ description: longDescription });
      render(<ActivityItem {...props} />);

      expect(screen.getByTestId('activity-description')).toHaveTextContent(longDescription);
    });

    test('handles special characters in metadata', () => {
      const props = createProps({
        metadata: { 'special-key': 'value with <html> & special chars' },
      });
      render(<ActivityItem {...props} />);

      fireEvent.click(screen.getByTestId('expand-button'));

      const metadataSection = screen.getByTestId('metadata-section');
      expect(metadataSection).toHaveTextContent('value with <html> & special chars');
    });
  });
});
