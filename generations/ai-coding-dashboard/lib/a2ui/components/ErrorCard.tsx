/**
 * ErrorCard Component
 * Displays errors with recovery options for human intervention
 * Part of A2UI Component Catalog
 */

'use client';

import React, { useState } from 'react';
import { ErrorCardProps } from '../types';
import { AlertOctagon, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';

export const ErrorCard: React.FC<ErrorCardProps> = ({
  errorId,
  message,
  details,
  recoveryOptions,
  stackTrace,
  onSelectRecovery,
  selectedRecovery,
  isPending = true,
  className = '',
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const [showStackTrace, setShowStackTrace] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleRecovery = (optionId: string) => {
    if (!isPending || submitting) return;
    setSubmitting(true);
    onSelectRecovery?.(optionId);
  };

  return (
    <div
      className={`rounded-lg border-2 border-red-600 bg-red-900/30 overflow-hidden ${className}`}
      role="alert"
      aria-label={`Error: ${message}`}
      data-testid="error-card"
      data-error-id={errorId}
    >
      {/* Header */}
      <div className="p-4 border-b border-red-800/50">
        <div className="flex items-start gap-3">
          <AlertOctagon className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-red-300">Error Encountered</h3>
            <p className="text-sm text-white mt-1 font-medium">{message}</p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Expandable details */}
        {details && (
          <div>
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1 text-xs font-semibold text-gray-400 uppercase tracking-wide
                hover:text-gray-300 transition-colors"
              aria-expanded={showDetails}
            >
              {showDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              Details
            </button>
            {showDetails && (
              <p className="mt-2 text-sm text-gray-300 leading-relaxed bg-gray-800/50 border border-gray-700 rounded-md p-3">
                {details}
              </p>
            )}
          </div>
        )}

        {/* Stack trace */}
        {stackTrace && (
          <div>
            <button
              onClick={() => setShowStackTrace(!showStackTrace)}
              className="flex items-center gap-1 text-xs font-semibold text-gray-400 uppercase tracking-wide
                hover:text-gray-300 transition-colors"
              aria-expanded={showStackTrace}
            >
              {showStackTrace ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              Stack Trace
            </button>
            {showStackTrace && (
              <pre className="mt-2 text-xs text-red-200 bg-gray-900 border border-red-800/50 rounded-md p-3
                overflow-x-auto font-mono max-h-40 overflow-y-auto">
                {stackTrace}
              </pre>
            )}
          </div>
        )}

        {/* Recovery options */}
        {recoveryOptions && recoveryOptions.length > 0 && isPending && (
          <div className="space-y-2 pt-2">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
              Recovery Options
            </h4>
            <div className="space-y-2">
              {recoveryOptions.map((option) => {
                const isSelected = selectedRecovery === option.id;
                return (
                  <button
                    key={option.id}
                    onClick={() => handleRecovery(option.id)}
                    disabled={submitting}
                    className={`w-full text-left p-3 rounded-lg border transition-all duration-200
                      ${isSelected
                        ? 'border-red-500 bg-red-800/40'
                        : 'border-gray-700 bg-gray-800/30 hover:border-gray-500'
                      }
                      disabled:opacity-50 disabled:cursor-not-allowed`}
                    data-testid={`recovery-option-${option.id}`}
                  >
                    <span className="text-sm font-semibold text-white">{option.label}</span>
                    {option.description && (
                      <p className="text-xs text-gray-400 mt-0.5">{option.description}</p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {submitting && (
          <div className="flex items-center gap-2 text-sm text-red-300">
            <Loader2 className="w-4 h-4 animate-spin" />
            Applying recovery...
          </div>
        )}

        {!isPending && selectedRecovery && (
          <div className="p-3 bg-gray-800/50 border border-gray-700 rounded-md">
            <span className="text-sm text-gray-400 italic">
              Recovery applied: {recoveryOptions?.find(o => o.id === selectedRecovery)?.label}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

ErrorCard.displayName = 'ErrorCard';

export default ErrorCard;
