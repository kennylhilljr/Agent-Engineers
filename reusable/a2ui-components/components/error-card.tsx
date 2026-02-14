import React, { useState } from 'react';
import { A2UIProps, A2UIEventType } from '@/lib/a2ui-types';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  AlertCircle,
  Info,
  AlertTriangle,
  XCircle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  X,
  Code,
} from 'lucide-react';

export type ErrorSeverity = 'info' | 'warning' | 'error' | 'critical';

export interface ErrorCardData {
  errorId?: string;
  title: string;
  message: string;
  errorCode?: string;
  severity?: ErrorSeverity;
  timestamp?: Date | string;
  stackTrace?: string;
  details?: Record<string, unknown>;
  actions?: ErrorAction[];
  onAction?: (actionId: string) => void;
  onDismiss?: () => void;
}

export interface ErrorAction {
  id: string;
  label: string;
  variant?: 'primary' | 'secondary' | 'destructive';
  icon?: string;
}

const severityConfig: Record<ErrorSeverity, {
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}> = {
  info: {
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    label: 'Info',
    icon: Info,
  },
  warning: {
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/30',
    label: 'Warning',
    icon: AlertTriangle,
  },
  error: {
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    label: 'Error',
    icon: AlertCircle,
  },
  critical: {
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/30',
    label: 'Critical',
    icon: XCircle,
  },
};

/**
 * ErrorCard - Display error messages with severity levels and recovery actions
 * Supports 4 severity levels: info, warning, error, critical
 * Features: collapsible stack trace, error code display, action buttons
 */
export function ErrorCard({ type, data, metadata, onEvent }: A2UIProps) {
  const errorData = data as unknown as ErrorCardData;
  const [stackTraceExpanded, setStackTraceExpanded] = useState(false);

  const severity = errorData.severity || 'error';
  const severityStyle = severityConfig[severity];
  const SeverityIcon = severityStyle.icon;

  const handleAction = (actionId: string) => {
    if (errorData.onAction) {
      errorData.onAction(actionId);
    }
    if (onEvent) {
      onEvent((A2UIEventType.CLICK as any) || 'action', { actionId });
    }
  };

  const handleDismiss = () => {
    if (errorData.onDismiss) {
      errorData.onDismiss();
    }
    if (onEvent) {
      onEvent((A2UIEventType.CLICK as any) || 'dismiss', {});
    }
  };

  const toggleStackTrace = () => {
    setStackTraceExpanded(!stackTraceExpanded);
    if (onEvent) {
      onEvent((A2UIEventType.CLICK as any) || 'toggle_stack', { expanded: !stackTraceExpanded });
    }
  };

  const formatTimestamp = (timestamp: Date | string | undefined) => {
    if (!timestamp) return null;
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const timestampFormatted = formatTimestamp(errorData.timestamp);

  return (
    <Card
      className={cn(
        "bg-gray-900 text-gray-100 overflow-hidden",
        "transition-all duration-300",
        severityStyle.borderColor,
        "hover:border-opacity-60"
      )}
      data-testid="error-card"
      data-severity={severity}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          {/* Icon and Title */}
          <div className="flex items-start gap-3 flex-1">
            <div className={cn("flex-shrink-0 mt-0.5", severityStyle.color)} data-testid="severity-icon">
              <SeverityIcon className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <CardTitle className="text-lg font-semibold mb-1 flex items-center gap-2 flex-wrap">
                <span className="break-words">{errorData.title}</span>
                {errorData.errorCode && (
                  <code
                    className="text-xs font-mono bg-gray-800 px-2 py-0.5 rounded border border-gray-700"
                    data-testid="error-code"
                  >
                    {errorData.errorCode}
                  </code>
                )}
              </CardTitle>
              {timestampFormatted && (
                <div className="text-xs text-gray-500 flex items-center gap-1" data-testid="timestamp">
                  <span>{timestampFormatted}</span>
                </div>
              )}
            </div>
          </div>

          {/* Severity Badge and Dismiss */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <Badge
              className={cn(
                "font-semibold uppercase text-xs px-2 py-0.5",
                severityStyle.bgColor,
                severityStyle.color,
                severityStyle.borderColor,
                "border"
              )}
              data-testid="severity-badge"
            >
              {severityStyle.label}
            </Badge>
            {errorData.onDismiss && (
              <button
                onClick={handleDismiss}
                className="text-gray-400 hover:text-gray-300 transition-colors"
                aria-label="Dismiss error"
                data-testid="dismiss-button"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Error Message */}
        <div className="text-sm text-gray-300" data-testid="error-message">
          {errorData.message}
        </div>

        {/* Error Details */}
        {errorData.details && Object.keys(errorData.details).length > 0 && (
          <div
            className="bg-gray-800/50 border border-gray-700 rounded-lg p-3"
            data-testid="error-details"
          >
            <div className="text-xs font-semibold text-gray-400 uppercase mb-2">
              Details
            </div>
            <div className="space-y-1">
              {Object.entries(errorData.details).map(([key, value]) => (
                <div key={key} className="text-xs">
                  <span className="text-gray-500">{key}:</span>{' '}
                  <span className="text-gray-300">
                    {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Stack Trace */}
        {errorData.stackTrace && (
          <div className="border border-gray-700 rounded-lg overflow-hidden" data-testid="stack-trace-container">
            <button
              onClick={toggleStackTrace}
              className={cn(
                "w-full flex items-center justify-between px-3 py-2 text-sm font-medium",
                "bg-gray-800 hover:bg-gray-750 transition-colors",
                "text-gray-300"
              )}
              data-testid="stack-trace-toggle"
              aria-expanded={stackTraceExpanded}
            >
              <div className="flex items-center gap-2">
                <Code className="w-4 h-4" />
                <span>Stack Trace</span>
              </div>
              {stackTraceExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            {stackTraceExpanded && (
              <div
                className="bg-gray-950 p-3 overflow-x-auto"
                data-testid="stack-trace-content"
              >
                <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap break-words">
                  {errorData.stackTrace}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Action Buttons */}
        {errorData.actions && errorData.actions.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2" data-testid="action-buttons">
            {errorData.actions.map((action) => {
              const variant = action.variant || 'secondary';
              const buttonStyles = {
                primary: 'bg-blue-600 hover:bg-blue-700 text-white',
                secondary: 'bg-gray-700 hover:bg-gray-600 text-gray-100',
                destructive: 'bg-red-600 hover:bg-red-700 text-white',
              };

              return (
                <Button
                  key={action.id}
                  onClick={() => handleAction(action.id)}
                  className={cn(
                    "text-sm px-3 py-1.5 rounded transition-colors",
                    buttonStyles[variant]
                  )}
                  data-testid={`action-${action.id}`}
                  size="sm"
                >
                  {action.icon === 'refresh' && <RefreshCw className="w-3 h-3 mr-1.5" />}
                  {action.label}
                </Button>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
