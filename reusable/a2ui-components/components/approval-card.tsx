'use client';

import React, { useState, useEffect } from 'react';
import { A2UIProps, ApprovalCardData, A2UIEventType } from '@/lib/a2ui-types';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import {
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  AlertCircle,
  Info,
  Zap,
  ThumbsUp,
  ThumbsDown,
  Loader2,
} from 'lucide-react';

/**
 * Severity level type for approval cards
 */
type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

/**
 * Approval status type
 */
type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired';

/**
 * Configuration for severity levels
 */
const severityConfig: Record<SeverityLevel, {
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
}> = {
  low: {
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/40',
    label: 'Low Risk',
    icon: Info,
    iconColor: 'text-blue-400',
  },
  medium: {
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/40',
    label: 'Medium Risk',
    icon: AlertTriangle,
    iconColor: 'text-yellow-400',
  },
  high: {
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/40',
    label: 'High Risk',
    icon: AlertCircle,
    iconColor: 'text-orange-400',
  },
  critical: {
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/40',
    label: 'Critical Risk',
    icon: Zap,
    iconColor: 'text-red-400',
  },
};

/**
 * Configuration for approval status
 */
const statusConfig: Record<ApprovalStatus, {
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
}> = {
  pending: {
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/40',
    label: 'Pending Approval',
    icon: Clock,
    iconColor: 'text-yellow-400',
  },
  approved: {
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500/40',
    label: 'Approved',
    icon: CheckCircle2,
    iconColor: 'text-green-400',
  },
  rejected: {
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/40',
    label: 'Rejected',
    icon: XCircle,
    iconColor: 'text-red-400',
  },
  expired: {
    color: 'text-gray-400',
    bgColor: 'bg-gray-500/10',
    borderColor: 'border-gray-500/40',
    label: 'Expired',
    icon: Clock,
    iconColor: 'text-gray-400',
  },
};

/**
 * ApprovalCard - Human-in-the-loop approval workflows
 *
 * A comprehensive approval card component with severity levels, deadline countdown,
 * optional reason input, and loading states.
 *
 * @component
 * @example
 * ```tsx
 * <ApprovalCard
 *   type="a2ui.ApprovalCard"
 *   data={{
 *     approvalId: 'apr-123',
 *     title: 'Delete Database Table',
 *     description: 'This action will permanently delete the user_sessions table',
 *     action: 'DROP TABLE user_sessions',
 *     severity: 'critical',
 *     deadline: '2026-02-14T12:00:00Z',
 *     metadata: { database: 'production', table: 'user_sessions' }
 *   }}
 *   onEvent={(type, payload) => console.log(type, payload)}
 * />
 * ```
 */
export function ApprovalCard({ type, data, metadata, onEvent }: A2UIProps) {
  const approvalData = data as unknown as ApprovalCardData;

  // State management
  const [reason, setReason] = useState<string>('');
  const [timeRemaining, setTimeRemaining] = useState<string>('');
  const [isLoading, setIsLoading] = useState(approvalData.loading || false);

  // Extract configuration
  const status = (approvalData.status || 'pending') as ApprovalStatus;
  const severity = (approvalData.severity || 'medium') as SeverityLevel;
  const severitySettings = severityConfig[severity];
  const statusSettings = statusConfig[status];
  const SeverityIcon = severitySettings.icon;
  const StatusIcon = statusSettings.icon;

  /**
   * Calculate and update deadline countdown
   */
  useEffect(() => {
    if (!approvalData.deadline || status !== 'pending') {
      return;
    }

    const updateCountdown = () => {
      const deadline = new Date(approvalData.deadline!);
      const now = new Date();
      const diff = deadline.getTime() - now.getTime();

      if (diff <= 0) {
        setTimeRemaining('Deadline passed');
        return;
      }

      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      if (days > 0) {
        setTimeRemaining(`${days}d ${hours}h remaining`);
      } else if (hours > 0) {
        setTimeRemaining(`${hours}h ${minutes}m remaining`);
      } else if (minutes > 0) {
        setTimeRemaining(`${minutes}m ${seconds}s remaining`);
      } else {
        setTimeRemaining(`${seconds}s remaining`);
      }
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);

    return () => clearInterval(interval);
  }, [approvalData.deadline, status]);

  /**
   * Handle approve action
   */
  const handleApprove = async () => {
    if (status !== 'pending' || isLoading) return;

    setIsLoading(true);

    // Call custom callback if provided
    if (approvalData.onApprove) {
      approvalData.onApprove(reason || undefined);
    }

    // Call onRespond callback if provided
    if (approvalData.onRespond) {
      approvalData.onRespond({ approved: true, reason: reason || undefined });
    }

    // Emit event
    if (onEvent) {
      onEvent(A2UIEventType.APPROVE as any, {
        approvalId: approvalData.approvalId,
        title: approvalData.title,
        action: approvalData.action,
        reason: reason || undefined,
        severity,
        timestamp: new Date().toISOString(),
      });
    }

    // Simulate async operation
    setTimeout(() => setIsLoading(false), 500);
  };

  /**
   * Handle reject action
   */
  const handleReject = async () => {
    if (status !== 'pending' || isLoading) return;

    setIsLoading(true);

    // Call custom callback if provided
    if (approvalData.onReject) {
      approvalData.onReject(reason || undefined);
    }

    // Call onRespond callback if provided
    if (approvalData.onRespond) {
      approvalData.onRespond({ approved: false, reason: reason || undefined });
    }

    // Emit event
    if (onEvent) {
      onEvent(A2UIEventType.REJECT as any, {
        approvalId: approvalData.approvalId,
        title: approvalData.title,
        action: approvalData.action,
        reason: reason || undefined,
        severity,
        timestamp: new Date().toISOString(),
      });
    }

    // Simulate async operation
    setTimeout(() => setIsLoading(false), 500);
  };

  /**
   * Render metadata section
   */
  const renderMetadata = () => {
    if (!approvalData.metadata || Object.keys(approvalData.metadata).length === 0) {
      return null;
    }

    return (
      <div className="space-y-2" data-testid="metadata-section">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
          Details
        </p>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(approvalData.metadata).map(([key, value]) => (
            <div key={key} className="text-sm" data-testid={`metadata-${key}`}>
              <span className="text-gray-500">{key}:</span>{' '}
              <span className="text-gray-300 font-medium">
                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <Card
      className={cn(
        'bg-gray-900 border-2 transition-all duration-300 shadow-lg',
        severitySettings.borderColor,
        severitySettings.bgColor
      )}
      data-testid="approval-card"
      data-severity={severity}
      data-status={status}
    >
      <CardHeader className="pb-3">
        {/* Header with title, severity, and status badges */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2 flex-1">
            <SeverityIcon
              className={cn('w-5 h-5 flex-shrink-0 mt-0.5', severitySettings.iconColor)}
              data-testid="severity-icon"
              aria-label={severitySettings.label}
            />
            <CardTitle className="text-lg font-semibold text-gray-100" data-testid="approval-title">
              {approvalData.title}
            </CardTitle>
          </div>
          <div className="flex gap-2">
            <Badge
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 border flex-shrink-0',
                severitySettings.bgColor,
                severitySettings.color,
                severitySettings.borderColor
              )}
              data-testid="severity-badge"
            >
              <span className="text-xs font-medium">{severitySettings.label}</span>
            </Badge>
            <Badge
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 border flex-shrink-0',
                statusSettings.bgColor,
                statusSettings.color,
                statusSettings.borderColor
              )}
              data-testid="status-badge"
            >
              <StatusIcon className="w-3.5 h-3.5" data-testid="status-icon" />
              <span className="text-xs font-medium">{statusSettings.label}</span>
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Description */}
        <p className="text-sm text-gray-300 leading-relaxed" data-testid="approval-description">
          {approvalData.description}
        </p>

        {/* Context (optional) */}
        {approvalData.context && (
          <div
            className="p-3 rounded-lg bg-gray-800/50 border border-gray-700"
            data-testid="context-section"
          >
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1">
              Context
            </p>
            <p className="text-sm text-gray-400">{approvalData.context}</p>
          </div>
        )}

        {/* Action highlight */}
        <div
          className={cn(
            'p-3 rounded-lg border-l-4',
            severitySettings.bgColor,
            severitySettings.borderColor
          )}
          data-testid="action-section"
        >
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1">
            Action Requested
          </p>
          <p className={cn('text-sm font-mono', severitySettings.color)} data-testid="action-text">
            {approvalData.action}
          </p>
        </div>

        {/* Metadata display */}
        {renderMetadata()}

        {/* Deadline countdown */}
        {approvalData.deadline && status === 'pending' && timeRemaining && (
          <div
            className="flex items-center gap-2 text-sm text-gray-400"
            data-testid="deadline-section"
          >
            <Clock className="w-4 h-4" />
            <span data-testid="deadline-countdown">{timeRemaining}</span>
          </div>
        )}

        {/* Reason input (if pending) */}
        {status === 'pending' && (
          <div className="space-y-2" data-testid="reason-section">
            <label
              htmlFor="approval-reason"
              className="text-xs text-gray-500 font-medium uppercase tracking-wide"
            >
              Reason (Optional)
            </label>
            <Input
              id="approval-reason"
              type="text"
              placeholder="Add a reason for your decision..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="bg-gray-800 border-gray-700 text-gray-100 placeholder:text-gray-500"
              data-testid="reason-input"
              disabled={isLoading}
            />
          </div>
        )}

        {/* Action buttons (if pending) or status message */}
        {status === 'pending' ? (
          <div className="flex gap-3 pt-2" data-testid="action-buttons">
            <button
              onClick={handleApprove}
              disabled={isLoading}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
                'bg-green-600 hover:bg-green-500 text-white font-medium',
                'transition-all duration-200 hover:shadow-lg hover:shadow-green-500/20',
                'focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 focus:ring-offset-gray-900',
                'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-green-600'
              )}
              data-testid="approve-button"
              aria-label="Approve request"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" data-testid="loading-spinner" />
              ) : (
                <ThumbsUp className="w-4 h-4" />
              )}
              <span>Approve</span>
            </button>
            <button
              onClick={handleReject}
              disabled={isLoading}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
                'bg-red-600 hover:bg-red-500 text-white font-medium',
                'transition-all duration-200 hover:shadow-lg hover:shadow-red-500/20',
                'focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:ring-offset-gray-900',
                'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-red-600'
              )}
              data-testid="reject-button"
              aria-label="Reject request"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" data-testid="loading-spinner" />
              ) : (
                <ThumbsDown className="w-4 h-4" />
              )}
              <span>Reject</span>
            </button>
          </div>
        ) : (
          <div
            className={cn(
              'flex items-center gap-2 px-4 py-3 rounded-lg border',
              statusSettings.bgColor,
              statusSettings.borderColor
            )}
            data-testid="status-message"
          >
            <StatusIcon className={cn('w-5 h-5', statusSettings.iconColor)} />
            <span className={cn('font-medium', statusSettings.color)}>
              {status === 'approved'
                ? 'This request has been approved'
                : status === 'expired'
                ? 'This approval request has expired'
                : 'This request has been rejected'}
            </span>
          </div>
        )}

        {/* Required approval indicator */}
        {approvalData.requiredApproval !== false && status === 'pending' && (
          <p className="text-xs text-gray-500 italic" data-testid="required-indicator">
            * This approval is required to proceed
          </p>
        )}
      </CardContent>
    </Card>
  );
}
