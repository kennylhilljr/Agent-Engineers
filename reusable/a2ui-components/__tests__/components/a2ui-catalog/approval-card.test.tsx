import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ApprovalCard } from '@/components/a2ui-catalog/approval-card';
import { A2UIEventType, A2UIEvent, ApprovalCardData } from '@/lib/a2ui-types';

// Mock timers for testing deadline countdown
jest.useFakeTimers();

describe('ApprovalCard Component', () => {
  const mockOnEvent = jest.fn();
  const mockOnApprove = jest.fn();
  const mockOnReject = jest.fn();
  const mockOnRespond = jest.fn();

  const baseData: ApprovalCardData = {
    approvalId: 'apr-123',
    title: 'Delete database backup',
    description: 'This action will permanently delete the database backup from 2024-01-15.',
    action: 'DROP TABLE backups_20240115',
    severity: 'high',
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.clearAllTimers();
  });

  describe('Basic Rendering', () => {
    it('should render approval card with all required fields', () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('approval-card')).toBeInTheDocument();
      expect(screen.getByTestId('approval-title')).toHaveTextContent('Delete database backup');
      expect(screen.getByTestId('approval-description')).toHaveTextContent(
        'This action will permanently delete the database backup from 2024-01-15.'
      );
    });

    it('should render action section with highlighted text', () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('action-section')).toBeInTheDocument();
      expect(screen.getByTestId('action-text')).toHaveTextContent('DROP TABLE backups_20240115');
    });

    it('should render context section when context is provided', () => {
      const dataWithContext = {
        ...baseData,
        context: 'This backup is from 2 years ago and is no longer needed for recovery.',
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithContext}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('context-section')).toBeInTheDocument();
      expect(screen.getByText('This backup is from 2 years ago and is no longer needed for recovery.')).toBeInTheDocument();
    });

    it('should not render context section when context is not provided', () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('context-section')).not.toBeInTheDocument();
    });
  });

  describe('Severity Levels', () => {
    it('should display low severity badge with blue styling', () => {
      const lowSeverityData = { ...baseData, severity: 'low' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={lowSeverityData}
          onEvent={mockOnEvent}
        />
      );

      const card = screen.getByTestId('approval-card');
      const severityBadge = screen.getByTestId('severity-badge');

      expect(card.getAttribute('data-severity')).toBe('low');
      expect(severityBadge).toHaveTextContent('Low Risk');
      expect(card.className).toContain('border-blue-500');
    });

    it('should display medium severity badge with yellow styling', () => {
      const mediumSeverityData = { ...baseData, severity: 'medium' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={mediumSeverityData}
          onEvent={mockOnEvent}
        />
      );

      const card = screen.getByTestId('approval-card');
      const severityBadge = screen.getByTestId('severity-badge');

      expect(card.getAttribute('data-severity')).toBe('medium');
      expect(severityBadge).toHaveTextContent('Medium Risk');
      expect(card.className).toContain('border-yellow-500');
    });

    it('should display high severity badge with orange styling', () => {
      const highSeverityData = { ...baseData, severity: 'high' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={highSeverityData}
          onEvent={mockOnEvent}
        />
      );

      const card = screen.getByTestId('approval-card');
      const severityBadge = screen.getByTestId('severity-badge');

      expect(card.getAttribute('data-severity')).toBe('high');
      expect(severityBadge).toHaveTextContent('High Risk');
      expect(card.className).toContain('border-orange-500');
    });

    it('should display critical severity badge with red styling', () => {
      const criticalSeverityData = { ...baseData, severity: 'critical' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={criticalSeverityData}
          onEvent={mockOnEvent}
        />
      );

      const card = screen.getByTestId('approval-card');
      const severityBadge = screen.getByTestId('severity-badge');

      expect(card.getAttribute('data-severity')).toBe('critical');
      expect(severityBadge).toHaveTextContent('Critical Risk');
      expect(card.className).toContain('border-red-500');
    });

    it('should default to medium severity when not provided', () => {
      const { severity, ...dataWithoutSeverity } = baseData;
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithoutSeverity}
          onEvent={mockOnEvent}
        />
      );

      const card = screen.getByTestId('approval-card');
      expect(card.getAttribute('data-severity')).toBe('medium');
    });

    it('should display severity icon for each severity level', () => {
      const severities: Array<'low' | 'medium' | 'high' | 'critical'> = ['low', 'medium', 'high', 'critical'];

      severities.forEach((severity) => {
        const { container } = render(
          <ApprovalCard
            type="a2ui.ApprovalCard"
            data={{ ...baseData, severity }}
            onEvent={mockOnEvent}
          />
        );

        expect(screen.getByTestId('severity-icon')).toBeInTheDocument();
        container.remove();
      });
    });
  });

  describe('Status States', () => {
    it('should display pending status badge correctly', () => {
      const pendingData = { ...baseData, status: 'pending' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={pendingData}
          onEvent={mockOnEvent}
        />
      );

      const statusBadge = screen.getByTestId('status-badge');
      expect(statusBadge).toHaveTextContent('Pending Approval');
      expect(screen.getByTestId('status-icon')).toBeInTheDocument();
    });

    it('should display approved status badge correctly', () => {
      const approvedData = { ...baseData, status: 'approved' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={approvedData}
          onEvent={mockOnEvent}
        />
      );

      const statusBadge = screen.getByTestId('status-badge');
      expect(statusBadge).toHaveTextContent('Approved');
      expect(screen.getByTestId('status-icon')).toBeInTheDocument();
    });

    it('should display rejected status badge correctly', () => {
      const rejectedData = { ...baseData, status: 'rejected' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={rejectedData}
          onEvent={mockOnEvent}
        />
      );

      const statusBadge = screen.getByTestId('status-badge');
      expect(statusBadge).toHaveTextContent('Rejected');
      expect(screen.getByTestId('status-icon')).toBeInTheDocument();
    });

    it('should default to pending status when not provided', () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('status-badge')).toHaveTextContent('Pending Approval');
    });
  });

  describe('Action Buttons', () => {
    it('should display approve and reject buttons when status is pending', () => {
      const pendingData = { ...baseData, status: 'pending' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={pendingData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('action-buttons')).toBeInTheDocument();
      expect(screen.getByTestId('approve-button')).toBeInTheDocument();
      expect(screen.getByTestId('reject-button')).toBeInTheDocument();
    });

    it('should not display action buttons when status is approved', () => {
      const approvedData = { ...baseData, status: 'approved' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={approvedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('action-buttons')).not.toBeInTheDocument();
      expect(screen.getByTestId('status-message')).toBeInTheDocument();
    });

    it('should not display action buttons when status is rejected', () => {
      const rejectedData = { ...baseData, status: 'rejected' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={rejectedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('action-buttons')).not.toBeInTheDocument();
      expect(screen.getByTestId('status-message')).toBeInTheDocument();
    });

    it('should emit APPROVE event when approve button is clicked', async () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      const approveButton = screen.getByTestId('approve-button');

      act(() => {
        fireEvent.click(approveButton);
      });

      await waitFor(() => {
        expect(mockOnEvent).toHaveBeenCalledWith(A2UIEvent.APPROVE, expect.objectContaining({
          approvalId: baseData.approvalId,
          title: baseData.title,
          action: baseData.action,
          severity: baseData.severity,
        }));
      });
    });

    it('should emit REJECT event when reject button is clicked', async () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      const rejectButton = screen.getByTestId('reject-button');

      act(() => {
        fireEvent.click(rejectButton);
      });

      await waitFor(() => {
        expect(mockOnEvent).toHaveBeenCalledWith(A2UIEvent.REJECT, expect.objectContaining({
          approvalId: baseData.approvalId,
          title: baseData.title,
          action: baseData.action,
          severity: baseData.severity,
        }));
      });
    });
  });

  describe('Reason Input', () => {
    it('should render reason input when status is pending', () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('reason-section')).toBeInTheDocument();
      expect(screen.getByTestId('reason-input')).toBeInTheDocument();
    });

    it('should not render reason input when status is approved', () => {
      const approvedData = { ...baseData, status: 'approved' as const };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={approvedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('reason-section')).not.toBeInTheDocument();
    });

    it('should update reason value when typing', () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      const reasonInput = screen.getByTestId('reason-input') as HTMLInputElement;
      fireEvent.change(reasonInput, { target: { value: 'This backup is outdated' } });

      expect(reasonInput.value).toBe('This backup is outdated');
    });

    it('should include reason in approve event payload', async () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      const reasonInput = screen.getByTestId('reason-input');
      fireEvent.change(reasonInput, { target: { value: 'Approved after verification' } });

      const approveButton = screen.getByTestId('approve-button');

      act(() => {
        fireEvent.click(approveButton);
      });

      await waitFor(() => {
        expect(mockOnEvent).toHaveBeenCalledWith(A2UIEvent.APPROVE, expect.objectContaining({
          reason: 'Approved after verification',
        }));
      });
    });

    it('should include reason in reject event payload', async () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      const reasonInput = screen.getByTestId('reason-input');
      fireEvent.change(reasonInput, { target: { value: 'Rejected for security reasons' } });

      const rejectButton = screen.getByTestId('reject-button');

      act(() => {
        fireEvent.click(rejectButton);
      });

      await waitFor(() => {
        expect(mockOnEvent).toHaveBeenCalledWith(A2UIEvent.REJECT, expect.objectContaining({
          reason: 'Rejected for security reasons',
        }));
      });
    });
  });

  describe('Loading States', () => {
    it('should display loading spinner when loading prop is true', () => {
      const loadingData = { ...baseData, loading: true };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      const approveButton = screen.getByTestId('approve-button');
      expect(approveButton).toBeDisabled();
      expect(screen.getAllByTestId('loading-spinner')).toHaveLength(2); // Both buttons show spinner
    });

    it('should disable buttons while loading', () => {
      const loadingData = { ...baseData, loading: true };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('approve-button')).toBeDisabled();
      expect(screen.getByTestId('reject-button')).toBeDisabled();
    });

    it('should show loading spinner after button click', async () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      const approveButton = screen.getByTestId('approve-button');

      act(() => {
        fireEvent.click(approveButton);
      });

      // Button should be disabled immediately
      expect(approveButton).toBeDisabled();
    });

    it('should disable reason input while loading', () => {
      const loadingData = { ...baseData, loading: true };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('reason-input')).toBeDisabled();
    });
  });

  describe('Metadata Display', () => {
    it('should display metadata section when metadata is provided', () => {
      const dataWithMetadata = {
        ...baseData,
        metadata: {
          database: 'production',
          table: 'backups_20240115',
          size: '2.5 GB',
        },
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithMetadata}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('metadata-section')).toBeInTheDocument();
      expect(screen.getByTestId('metadata-database')).toHaveTextContent('production');
      expect(screen.getByTestId('metadata-table')).toHaveTextContent('backups_20240115');
      expect(screen.getByTestId('metadata-size')).toHaveTextContent('2.5 GB');
    });

    it('should not display metadata section when metadata is empty', () => {
      const dataWithEmptyMetadata = {
        ...baseData,
        metadata: {},
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithEmptyMetadata}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('metadata-section')).not.toBeInTheDocument();
    });

    it('should not display metadata section when metadata is not provided', () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('metadata-section')).not.toBeInTheDocument();
    });

    it('should handle object values in metadata', () => {
      const dataWithComplexMetadata = {
        ...baseData,
        metadata: {
          config: { retries: 3, timeout: 5000 },
        },
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithComplexMetadata}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('metadata-config')).toHaveTextContent('{"retries":3,"timeout":5000}');
    });
  });

  describe('Deadline Countdown', () => {
    beforeEach(() => {
      jest.useFakeTimers();
      jest.setSystemTime(new Date('2026-02-13T12:00:00Z'));
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should display deadline countdown when deadline is provided and status is pending', () => {
      const dataWithDeadline = {
        ...baseData,
        deadline: new Date('2026-02-13T14:30:00Z').toISOString(), // 2.5 hours from now
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithDeadline}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('deadline-section')).toBeInTheDocument();
      expect(screen.getByTestId('deadline-countdown')).toHaveTextContent(/remaining/);
    });

    it('should not display deadline when status is not pending', () => {
      const approvedDataWithDeadline = {
        ...baseData,
        status: 'approved' as const,
        deadline: new Date('2026-02-13T14:00:00Z').toISOString(),
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={approvedDataWithDeadline}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('deadline-section')).not.toBeInTheDocument();
    });

    it('should display "Deadline passed" when deadline is in the past', () => {
      const dataWithPastDeadline = {
        ...baseData,
        deadline: new Date('2026-02-13T10:00:00Z').toISOString(), // 2 hours ago
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithPastDeadline}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('deadline-countdown')).toHaveTextContent('Deadline passed');
    });

    it('should format countdown with days when more than 24 hours remain', () => {
      const dataWithDeadline = {
        ...baseData,
        deadline: new Date('2026-02-15T12:00:00Z').toISOString(), // 2 days from now
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithDeadline}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('deadline-countdown')).toHaveTextContent(/\d+d \d+h remaining/);
    });

    it('should format countdown with hours when less than 24 hours remain', () => {
      const dataWithDeadline = {
        ...baseData,
        deadline: new Date('2026-02-13T15:30:00Z').toISOString(), // 3.5 hours from now
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithDeadline}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('deadline-countdown')).toHaveTextContent(/\d+h \d+m remaining/);
    });
  });

  describe('Callbacks', () => {
    it('should call onApprove callback when approve button is clicked', async () => {
      const dataWithCallback = {
        ...baseData,
        onApprove: mockOnApprove,
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithCallback}
          onEvent={mockOnEvent}
        />
      );

      const approveButton = screen.getByTestId('approve-button');

      act(() => {
        fireEvent.click(approveButton);
      });

      await waitFor(() => {
        expect(mockOnApprove).toHaveBeenCalled();
      });
    });

    it('should call onReject callback when reject button is clicked', async () => {
      const dataWithCallback = {
        ...baseData,
        onReject: mockOnReject,
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithCallback}
          onEvent={mockOnEvent}
        />
      );

      const rejectButton = screen.getByTestId('reject-button');

      act(() => {
        fireEvent.click(rejectButton);
      });

      await waitFor(() => {
        expect(mockOnReject).toHaveBeenCalled();
      });
    });

    it('should call onRespond callback with approved=true when approve button is clicked', async () => {
      const dataWithCallback = {
        ...baseData,
        onRespond: mockOnRespond,
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithCallback}
          onEvent={mockOnEvent}
        />
      );

      const approveButton = screen.getByTestId('approve-button');

      act(() => {
        fireEvent.click(approveButton);
      });

      await waitFor(() => {
        expect(mockOnRespond).toHaveBeenCalledWith(expect.objectContaining({
          approved: true,
        }));
      });
    });

    it('should call onRespond callback with approved=false when reject button is clicked', async () => {
      const dataWithCallback = {
        ...baseData,
        onRespond: mockOnRespond,
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithCallback}
          onEvent={mockOnEvent}
        />
      );

      const rejectButton = screen.getByTestId('reject-button');

      act(() => {
        fireEvent.click(rejectButton);
      });

      await waitFor(() => {
        expect(mockOnRespond).toHaveBeenCalledWith(expect.objectContaining({
          approved: false,
        }));
      });
    });
  });

  describe('Required Approval Indicator', () => {
    it('should display required approval indicator by default when pending', () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('required-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('required-indicator')).toHaveTextContent('* This approval is required to proceed');
    });

    it('should not display required approval indicator when requiredApproval is false', () => {
      const optionalApprovalData = {
        ...baseData,
        requiredApproval: false,
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={optionalApprovalData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('required-indicator')).not.toBeInTheDocument();
    });

    it('should not display required approval indicator when status is not pending', () => {
      const approvedData = {
        ...baseData,
        status: 'approved' as const,
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={approvedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('required-indicator')).not.toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing onEvent callback gracefully', () => {
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={baseData}
        />
      );

      const approveButton = screen.getByTestId('approve-button');

      expect(() => {
        fireEvent.click(approveButton);
      }).not.toThrow();
    });

    it('should handle long description text', () => {
      const longDescription = 'A'.repeat(500);
      const dataWithLongDesc = {
        ...baseData,
        description: longDescription,
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithLongDesc}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('approval-description')).toHaveTextContent(longDescription);
    });

    it('should handle long action text', () => {
      const longAction = 'DROP TABLE ' + 'very_long_table_name_'.repeat(20);
      const dataWithLongAction = {
        ...baseData,
        action: longAction,
      };

      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={dataWithLongAction}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('action-text')).toHaveTextContent(longAction);
    });

    it('should not trigger action when button is clicked while loading', async () => {
      const loadingData = { ...baseData, loading: true };
      render(
        <ApprovalCard
          type="a2ui.ApprovalCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      const approveButton = screen.getByTestId('approve-button');
      fireEvent.click(approveButton);

      // Wait to ensure no event is triggered
      await new Promise(resolve => setTimeout(resolve, 100));

      expect(mockOnEvent).not.toHaveBeenCalled();
    });

    it('should handle all severity and status combinations', () => {
      const severities: Array<'low' | 'medium' | 'high' | 'critical'> = ['low', 'medium', 'high', 'critical'];
      const statuses: Array<'pending' | 'approved' | 'rejected'> = ['pending', 'approved', 'rejected'];

      severities.forEach((severity) => {
        statuses.forEach((status) => {
          const { container } = render(
            <ApprovalCard
              type="a2ui.ApprovalCard"
              data={{ ...baseData, severity, status }}
              onEvent={mockOnEvent}
            />
          );

          const card = screen.getByTestId('approval-card');
          expect(card.getAttribute('data-severity')).toBe(severity);
          expect(card.getAttribute('data-status')).toBe(status);

          container.remove();
        });
      });
    });
  });
});
