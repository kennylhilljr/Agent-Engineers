import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ErrorCard } from '@/components/a2ui-catalog/error-card';

describe('ErrorCard Component', () => {
  const mockOnEvent = jest.fn();
  const mockOnAction = jest.fn();
  const mockOnDismiss = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  const createProps = (overrides = {}) => ({
    type: 'a2ui.ErrorCard',
    data: {
      title: 'Test Error',
      message: 'This is a test error message',
      ...overrides,
    },
    onEvent: mockOnEvent,
  });

  describe('Basic Rendering', () => {
    it('renders error card with title and message', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.getByText('Test Error')).toBeInTheDocument();
      expect(screen.getByText('This is a test error message')).toBeInTheDocument();
    });

    it('renders with error-card test id', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.getByTestId('error-card')).toBeInTheDocument();
    });

    it('renders error message with correct test id', () => {
      render(<ErrorCard {...createProps()} />);

      const errorMessage = screen.getByTestId('error-message');
      expect(errorMessage).toHaveTextContent('This is a test error message');
    });

    it('renders with default error severity when not specified', () => {
      render(<ErrorCard {...createProps()} />);

      const card = screen.getByTestId('error-card');
      expect(card).toHaveAttribute('data-severity', 'error');
    });

    it('renders severity icon', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.getByTestId('severity-icon')).toBeInTheDocument();
    });

    it('renders severity badge', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.getByTestId('severity-badge')).toBeInTheDocument();
    });
  });

  describe('Severity Levels', () => {
    it('renders info severity correctly', () => {
      render(<ErrorCard {...createProps({ severity: 'info' })} />);

      const card = screen.getByTestId('error-card');
      expect(card).toHaveAttribute('data-severity', 'info');
      expect(screen.getByTestId('severity-badge')).toHaveTextContent('Info');
    });

    it('renders warning severity correctly', () => {
      render(<ErrorCard {...createProps({ severity: 'warning' })} />);

      const card = screen.getByTestId('error-card');
      expect(card).toHaveAttribute('data-severity', 'warning');
      expect(screen.getByTestId('severity-badge')).toHaveTextContent('Warning');
    });

    it('renders error severity correctly', () => {
      render(<ErrorCard {...createProps({ severity: 'error' })} />);

      const card = screen.getByTestId('error-card');
      expect(card).toHaveAttribute('data-severity', 'error');
      expect(screen.getByTestId('severity-badge')).toHaveTextContent('Error');
    });

    it('renders critical severity correctly', () => {
      render(<ErrorCard {...createProps({ severity: 'critical' })} />);

      const card = screen.getByTestId('error-card');
      expect(card).toHaveAttribute('data-severity', 'critical');
      expect(screen.getByTestId('severity-badge')).toHaveTextContent('Critical');
    });

    it('applies correct CSS classes for info severity', () => {
      render(<ErrorCard {...createProps({ severity: 'info' })} />);

      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('bg-blue-500/10', 'text-blue-400');
    });

    it('applies correct CSS classes for warning severity', () => {
      render(<ErrorCard {...createProps({ severity: 'warning' })} />);

      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('bg-yellow-500/10', 'text-yellow-400');
    });

    it('applies correct CSS classes for error severity', () => {
      render(<ErrorCard {...createProps({ severity: 'error' })} />);

      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('bg-red-500/10', 'text-red-400');
    });

    it('applies correct CSS classes for critical severity', () => {
      render(<ErrorCard {...createProps({ severity: 'critical' })} />);

      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('bg-purple-500/10', 'text-purple-400');
    });
  });

  describe('Error Code Display', () => {
    it('renders error code when provided', () => {
      render(<ErrorCard {...createProps({ errorCode: 'ERR-500' })} />);

      expect(screen.getByTestId('error-code')).toHaveTextContent('ERR-500');
    });

    it('does not render error code section when not provided', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.queryByTestId('error-code')).not.toBeInTheDocument();
    });

    it('renders error code with monospace font', () => {
      render(<ErrorCard {...createProps({ errorCode: 'ERR-404' })} />);

      const errorCode = screen.getByTestId('error-code');
      expect(errorCode).toHaveClass('font-mono');
    });
  });

  describe('Timestamp Display', () => {
    it('renders timestamp when provided as Date object', () => {
      const timestamp = new Date('2024-01-15T10:30:00Z');
      render(<ErrorCard {...createProps({ timestamp })} />);

      expect(screen.getByTestId('timestamp')).toBeInTheDocument();
    });

    it('renders timestamp when provided as string', () => {
      render(<ErrorCard {...createProps({ timestamp: '2024-01-15T10:30:00Z' })} />);

      expect(screen.getByTestId('timestamp')).toBeInTheDocument();
    });

    it('does not render timestamp when not provided', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.queryByTestId('timestamp')).not.toBeInTheDocument();
    });

    it('formats timestamp correctly', () => {
      const timestamp = new Date('2024-01-15T10:30:45Z');
      render(<ErrorCard {...createProps({ timestamp })} />);

      const timestampEl = screen.getByTestId('timestamp');
      expect(timestampEl.textContent).toContain('2024');
      expect(timestampEl.textContent).toContain('Jan');
    });
  });

  describe('Error Details', () => {
    it('renders error details when provided', () => {
      const details = {
        url: '/api/users',
        method: 'POST',
        statusCode: 500,
      };
      render(<ErrorCard {...createProps({ details })} />);

      expect(screen.getByTestId('error-details')).toBeInTheDocument();
    });

    it('does not render details section when empty', () => {
      render(<ErrorCard {...createProps({ details: {} })} />);

      expect(screen.queryByTestId('error-details')).not.toBeInTheDocument();
    });

    it('does not render details section when not provided', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.queryByTestId('error-details')).not.toBeInTheDocument();
    });

    it('renders all detail key-value pairs', () => {
      const details = {
        url: '/api/users',
        method: 'POST',
        statusCode: 500,
      };
      render(<ErrorCard {...createProps({ details })} />);

      const detailsEl = screen.getByTestId('error-details');
      expect(within(detailsEl).getByText('url:')).toBeInTheDocument();
      expect(within(detailsEl).getByText('/api/users')).toBeInTheDocument();
      expect(within(detailsEl).getByText('method:')).toBeInTheDocument();
      expect(within(detailsEl).getByText('POST')).toBeInTheDocument();
    });

    it('renders object values as JSON strings', () => {
      const details = {
        config: { timeout: 5000, retry: true },
      };
      render(<ErrorCard {...createProps({ details })} />);

      const detailsEl = screen.getByTestId('error-details');
      expect(within(detailsEl).getByText(/timeout.*5000/)).toBeInTheDocument();
    });
  });

  describe('Stack Trace', () => {
    const stackTrace = `Error: Failed to fetch
  at fetchData (app.js:10:5)
  at handleRequest (server.js:45:12)
  at process._tickCallback (internal/process/next_tick.js:68:7)`;

    it('renders stack trace toggle button when stack trace provided', () => {
      render(<ErrorCard {...createProps({ stackTrace })} />);

      expect(screen.getByTestId('stack-trace-toggle')).toBeInTheDocument();
    });

    it('does not render stack trace when not provided', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.queryByTestId('stack-trace-container')).not.toBeInTheDocument();
    });

    it('stack trace is collapsed by default', () => {
      render(<ErrorCard {...createProps({ stackTrace })} />);

      expect(screen.queryByTestId('stack-trace-content')).not.toBeInTheDocument();
    });

    it('expands stack trace when toggle is clicked', () => {
      render(<ErrorCard {...createProps({ stackTrace })} />);

      const toggle = screen.getByTestId('stack-trace-toggle');
      fireEvent.click(toggle);

      expect(screen.getByTestId('stack-trace-content')).toBeInTheDocument();
    });

    it('collapses stack trace when toggle is clicked again', () => {
      render(<ErrorCard {...createProps({ stackTrace })} />);

      const toggle = screen.getByTestId('stack-trace-toggle');
      fireEvent.click(toggle);
      expect(screen.getByTestId('stack-trace-content')).toBeInTheDocument();

      fireEvent.click(toggle);
      expect(screen.queryByTestId('stack-trace-content')).not.toBeInTheDocument();
    });

    it('renders full stack trace content', () => {
      render(<ErrorCard {...createProps({ stackTrace })} />);

      const toggle = screen.getByTestId('stack-trace-toggle');
      fireEvent.click(toggle);

      const content = screen.getByTestId('stack-trace-content');
      expect(content).toHaveTextContent('Error: Failed to fetch');
      expect(content).toHaveTextContent('at fetchData (app.js:10:5)');
    });

    it('fires onEvent when stack trace is toggled', () => {
      render(<ErrorCard {...createProps({ stackTrace })} />);

      const toggle = screen.getByTestId('stack-trace-toggle');
      fireEvent.click(toggle);

      expect(mockOnEvent).toHaveBeenCalledWith('toggle_stack', { expanded: true });
    });

    it('sets aria-expanded attribute correctly', () => {
      render(<ErrorCard {...createProps({ stackTrace })} />);

      const toggle = screen.getByTestId('stack-trace-toggle');
      expect(toggle).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(toggle);
      expect(toggle).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('Action Buttons', () => {
    const actions = [
      { id: 'retry', label: 'Retry', variant: 'primary' as const, icon: 'refresh' },
      { id: 'dismiss', label: 'Dismiss', variant: 'secondary' as const },
      { id: 'report', label: 'Report Issue', variant: 'destructive' as const },
    ];

    it('renders action buttons when provided', () => {
      render(<ErrorCard {...createProps({ actions, onAction: mockOnAction })} />);

      expect(screen.getByTestId('action-buttons')).toBeInTheDocument();
    });

    it('does not render action buttons section when not provided', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.queryByTestId('action-buttons')).not.toBeInTheDocument();
    });

    it('renders all action buttons', () => {
      render(<ErrorCard {...createProps({ actions, onAction: mockOnAction })} />);

      expect(screen.getByTestId('action-retry')).toBeInTheDocument();
      expect(screen.getByTestId('action-dismiss')).toBeInTheDocument();
      expect(screen.getByTestId('action-report')).toBeInTheDocument();
    });

    it('renders action button labels', () => {
      render(<ErrorCard {...createProps({ actions, onAction: mockOnAction })} />);

      expect(screen.getByText('Retry')).toBeInTheDocument();
      expect(screen.getByText('Dismiss')).toBeInTheDocument();
      expect(screen.getByText('Report Issue')).toBeInTheDocument();
    });

    it('calls onAction when action button is clicked', () => {
      render(<ErrorCard {...createProps({ actions, onAction: mockOnAction })} />);

      const retryButton = screen.getByTestId('action-retry');
      fireEvent.click(retryButton);

      expect(mockOnAction).toHaveBeenCalledWith('retry');
    });

    it('fires onEvent when action button is clicked', () => {
      render(<ErrorCard {...createProps({ actions, onAction: mockOnAction })} />);

      const retryButton = screen.getByTestId('action-retry');
      fireEvent.click(retryButton);

      expect(mockOnEvent).toHaveBeenCalledWith('action', { actionId: 'retry' });
    });

    it('applies primary variant styles', () => {
      const primaryAction = [{ id: 'save', label: 'Save', variant: 'primary' as const }];
      render(<ErrorCard {...createProps({ actions: primaryAction, onAction: mockOnAction })} />);

      const button = screen.getByTestId('action-save');
      expect(button).toHaveClass('bg-blue-600');
    });

    it('applies secondary variant styles', () => {
      const secondaryAction = [{ id: 'cancel', label: 'Cancel', variant: 'secondary' as const }];
      render(<ErrorCard {...createProps({ actions: secondaryAction, onAction: mockOnAction })} />);

      const button = screen.getByTestId('action-cancel');
      expect(button).toHaveClass('bg-gray-700');
    });

    it('applies destructive variant styles', () => {
      const destructiveAction = [{ id: 'delete', label: 'Delete', variant: 'destructive' as const }];
      render(<ErrorCard {...createProps({ actions: destructiveAction, onAction: mockOnAction })} />);

      const button = screen.getByTestId('action-delete');
      expect(button).toHaveClass('bg-red-600');
    });

    it('defaults to secondary variant when not specified', () => {
      const defaultAction = [{ id: 'ok', label: 'OK' }];
      render(<ErrorCard {...createProps({ actions: defaultAction, onAction: mockOnAction })} />);

      const button = screen.getByTestId('action-ok');
      expect(button).toHaveClass('bg-gray-700');
    });

    it('renders refresh icon for action with icon="refresh"', () => {
      const actionWithIcon = [{ id: 'retry', label: 'Retry', icon: 'refresh' }];
      const { container } = render(<ErrorCard {...createProps({ actions: actionWithIcon, onAction: mockOnAction })} />);

      const button = screen.getByTestId('action-retry');
      const svg = button.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  describe('Dismiss Functionality', () => {
    it('renders dismiss button when onDismiss is provided', () => {
      render(<ErrorCard {...createProps({ onDismiss: mockOnDismiss })} />);

      expect(screen.getByTestId('dismiss-button')).toBeInTheDocument();
    });

    it('does not render dismiss button when onDismiss is not provided', () => {
      render(<ErrorCard {...createProps()} />);

      expect(screen.queryByTestId('dismiss-button')).not.toBeInTheDocument();
    });

    it('calls onDismiss when dismiss button is clicked', () => {
      render(<ErrorCard {...createProps({ onDismiss: mockOnDismiss })} />);

      const dismissButton = screen.getByTestId('dismiss-button');
      fireEvent.click(dismissButton);

      expect(mockOnDismiss).toHaveBeenCalled();
    });

    it('fires onEvent when dismiss button is clicked', () => {
      render(<ErrorCard {...createProps({ onDismiss: mockOnDismiss })} />);

      const dismissButton = screen.getByTestId('dismiss-button');
      fireEvent.click(dismissButton);

      expect(mockOnEvent).toHaveBeenCalledWith('dismiss', {});
    });

    it('has correct aria-label for dismiss button', () => {
      render(<ErrorCard {...createProps({ onDismiss: mockOnDismiss })} />);

      const dismissButton = screen.getByTestId('dismiss-button');
      expect(dismissButton).toHaveAttribute('aria-label', 'Dismiss error');
    });
  });

  describe('Edge Cases', () => {
    it('handles missing data gracefully', () => {
      const minimalProps: A2UIProps = {
        type: 'a2ui.ErrorCard',
        data: {
          title: 'Error',
          message: 'Message',
        },
      };

      expect(() => render(<ErrorCard {...minimalProps} />)).not.toThrow();
    });

    it('handles very long error messages', () => {
      const longMessage = 'This is a very long error message that should be displayed correctly. '.repeat(20);
      render(<ErrorCard {...createProps({ message: longMessage })} />);

      const errorMessage = screen.getByTestId('error-message');
      expect(errorMessage.textContent).toContain('This is a very long error message');
      expect(errorMessage.textContent.length).toBeGreaterThan(100);
    });

    it('handles empty actions array', () => {
      render(<ErrorCard {...createProps({ actions: [] })} />);

      expect(screen.queryByTestId('action-buttons')).not.toBeInTheDocument();
    });

    it('handles special characters in error code', () => {
      render(<ErrorCard {...createProps({ errorCode: 'ERR-500-#@!' })} />);

      expect(screen.getByTestId('error-code')).toHaveTextContent('ERR-500-#@!');
    });

    it('handles multiline stack traces', () => {
      const multilineStack = 'Line 1\nLine 2\nLine 3';
      render(<ErrorCard {...createProps({ stackTrace: multilineStack })} />);

      const toggle = screen.getByTestId('stack-trace-toggle');
      fireEvent.click(toggle);

      const content = screen.getByTestId('stack-trace-content');
      expect(content).toHaveTextContent('Line 1');
      expect(content).toHaveTextContent('Line 2');
      expect(content).toHaveTextContent('Line 3');
    });

    it('handles numeric detail values', () => {
      const details = { statusCode: 404, retryCount: 3 };
      render(<ErrorCard {...createProps({ details })} />);

      const detailsEl = screen.getByTestId('error-details');
      expect(within(detailsEl).getByText('404')).toBeInTheDocument();
      expect(within(detailsEl).getByText('3')).toBeInTheDocument();
    });

    it('handles boolean detail values', () => {
      const details = { isRetryable: true, isCritical: false };
      render(<ErrorCard {...createProps({ details })} />);

      const detailsEl = screen.getByTestId('error-details');
      expect(within(detailsEl).getByText('true')).toBeInTheDocument();
      expect(within(detailsEl).getByText('false')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper semantic HTML structure', () => {
      render(<ErrorCard {...createProps({ onDismiss: mockOnDismiss })} />);

      const dismissButton = screen.getByLabelText('Dismiss error');
      expect(dismissButton).toBeInTheDocument();
    });

    it('stack trace toggle has proper aria attributes', () => {
      const stackTrace = 'Error stack';
      render(<ErrorCard {...createProps({ stackTrace })} />);

      const toggle = screen.getByTestId('stack-trace-toggle');
      expect(toggle).toHaveAttribute('aria-expanded');
    });

    it('action buttons are keyboard accessible', () => {
      const actions = [{ id: 'retry', label: 'Retry' }];
      render(<ErrorCard {...createProps({ actions, onAction: mockOnAction })} />);

      const button = screen.getByTestId('action-retry');
      expect(button.tagName).toBe('BUTTON');
    });
  });

  describe('Integration', () => {
    it('renders complete error card with all features', () => {
      const completeProps = createProps({
        title: 'Database Connection Error',
        message: 'Failed to connect to database',
        errorCode: 'DB-ERR-500',
        severity: 'critical',
        timestamp: new Date('2024-01-15T10:30:00Z'),
        stackTrace: 'Error: Connection timeout\n  at connect (db.js:10:5)',
        details: { host: 'localhost', port: 5432, timeout: 5000 },
        actions: [
          { id: 'retry', label: 'Retry Connection', variant: 'primary' as const, icon: 'refresh' },
          { id: 'fallback', label: 'Use Fallback DB', variant: 'secondary' as const },
        ],
        onAction: mockOnAction,
        onDismiss: mockOnDismiss,
      });

      render(<ErrorCard {...completeProps} />);

      // Verify all sections are rendered
      expect(screen.getByText('Database Connection Error')).toBeInTheDocument();
      expect(screen.getByText('Failed to connect to database')).toBeInTheDocument();
      expect(screen.getByTestId('error-code')).toHaveTextContent('DB-ERR-500');
      expect(screen.getByTestId('severity-badge')).toHaveTextContent('Critical');
      expect(screen.getByTestId('timestamp')).toBeInTheDocument();
      expect(screen.getByTestId('error-details')).toBeInTheDocument();
      expect(screen.getByTestId('stack-trace-toggle')).toBeInTheDocument();
      expect(screen.getByTestId('action-buttons')).toBeInTheDocument();
      expect(screen.getByTestId('dismiss-button')).toBeInTheDocument();
    });

    it('handles multiple actions with different variants', () => {
      const multiActions = [
        { id: 'primary', label: 'Primary', variant: 'primary' as const },
        { id: 'secondary', label: 'Secondary', variant: 'secondary' as const },
        { id: 'destructive', label: 'Destructive', variant: 'destructive' as const },
      ];

      render(<ErrorCard {...createProps({ actions: multiActions, onAction: mockOnAction })} />);

      expect(screen.getByTestId('action-primary')).toHaveClass('bg-blue-600');
      expect(screen.getByTestId('action-secondary')).toHaveClass('bg-gray-700');
      expect(screen.getByTestId('action-destructive')).toHaveClass('bg-red-600');
    });
  });
});
