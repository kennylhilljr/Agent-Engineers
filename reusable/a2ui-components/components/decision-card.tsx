'use client';

import React, { useState } from 'react';
import { A2UIProps, DecisionCardData, A2UIEventType } from '@/lib/a2ui-types';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import {
  CheckCircle2,
  Circle,
  HelpCircle,
  Sparkles,
  Loader2,
  MessageSquare,
  XCircle,
} from 'lucide-react';

/**
 * Decision status type
 */
type DecisionStatus = 'pending' | 'decided' | 'timeout' | 'skipped';

/**
 * Configuration for decision status
 */
const statusConfig: Record<DecisionStatus, {
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
}> = {
  pending: {
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/40',
    label: 'Pending Decision',
    icon: HelpCircle,
    iconColor: 'text-blue-400',
  },
  decided: {
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500/40',
    label: 'Decided',
    icon: CheckCircle2,
    iconColor: 'text-green-400',
  },
  timeout: {
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/40',
    label: 'Timed Out',
    icon: XCircle,
    iconColor: 'text-orange-400',
  },
  skipped: {
    color: 'text-gray-400',
    bgColor: 'bg-gray-500/10',
    borderColor: 'border-gray-500/40',
    label: 'Skipped',
    icon: Circle,
    iconColor: 'text-gray-400',
  },
};

/**
 * DecisionCard - AI agents present decision options to users
 *
 * A comprehensive decision card component for presenting multiple choice decisions
 * with recommendations, context, and optional reasoning input.
 *
 * @component
 * @example
 * ```tsx
 * <DecisionCard
 *   type="a2ui.DecisionCard"
 *   data={{
 *     decisionId: 'dec-123',
 *     question: 'Which database should we use for this feature?',
 *     options: [
 *       { id: 'pg', label: 'PostgreSQL', description: 'Relational, ACID compliant', recommended: true },
 *       { id: 'mongo', label: 'MongoDB', description: 'Document store, flexible schema' },
 *       { id: 'redis', label: 'Redis', description: 'In-memory, fast caching' }
 *     ],
 *     recommendation: 'PostgreSQL is recommended for its reliability and transaction support',
 *     context: 'This feature requires strong consistency and relational data modeling'
 *   }}
 *   onEvent={(type, payload) => console.log(type, payload)}
 * />
 * ```
 */
export function DecisionCard({ type, data, metadata, onEvent }: A2UIProps) {
  const decisionData = data as unknown as DecisionCardData;

  // State management
  const [selectedOption, setSelectedOption] = useState<string | undefined>(
    decisionData.selectedOptionId
  );
  const [reasoning, setReasoning] = useState<string>('');
  const [isLoading, setIsLoading] = useState(decisionData.loading || false);

  // Extract configuration
  const status = (decisionData.status || 'pending') as DecisionStatus;
  const statusSettings = statusConfig[status] || statusConfig.pending;
  const StatusIcon = statusSettings?.icon || HelpCircle;

  /**
   * Handle option selection
   */
  const handleOptionSelect = (optionId: string) => {
    if (status !== 'pending' || isLoading) return;

    setSelectedOption(optionId);

    // Call custom callback if provided
    if (decisionData.onSelect) {
      decisionData.onSelect(optionId);
    }

    // Emit event
    if (onEvent) {
      onEvent(A2UIEventType.SELECT, {
        decisionId: decisionData.decisionId,
        question: decisionData.question,
        optionId,
        timestamp: new Date().toISOString(),
      });
    }
  };

  /**
   * Handle decision submission
   */
  const handleSubmit = async () => {
    if (status !== 'pending' || isLoading || !selectedOption) return;

    setIsLoading(true);

    // Call onRespond callback if provided
    if (decisionData.onRespond) {
      decisionData.onRespond({
        optionId: selectedOption,
        reasoning: reasoning || undefined,
      });
    }

    // Emit event
    if (onEvent) {
      onEvent(A2UIEventType.SUBMIT, {
        decisionId: decisionData.decisionId,
        question: decisionData.question,
        optionId: selectedOption,
        reasoning: reasoning || undefined,
        timestamp: new Date().toISOString(),
      });
    }

    // Simulate async operation
    setTimeout(() => setIsLoading(false), 500);
  };

  /**
   * Render recommendation section
   */
  const renderRecommendation = () => {
    if (!decisionData.recommendation) return null;

    return (
      <div
        className="flex items-start gap-3 p-3 rounded-lg bg-purple-500/10 border border-purple-500/40"
        data-testid="recommendation-section"
      >
        <Sparkles className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" data-testid="recommendation-icon" />
        <div className="flex-1">
          <p className="text-xs text-purple-400 font-medium uppercase tracking-wide mb-1">
            AI Recommendation
          </p>
          <p className="text-sm text-purple-200" data-testid="recommendation-text">
            {decisionData.recommendation}
          </p>
        </div>
      </div>
    );
  };

  /**
   * Render options as radio button cards
   */
  const renderOptions = () => {
    return (
      <div className="space-y-3" data-testid="options-section">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
          Select an option
        </p>
        {decisionData.options.map((option) => {
          const isSelected = selectedOption === option.id;
          const isRecommended = option.recommended;

          return (
            <button
              key={option.id}
              onClick={() => handleOptionSelect(option.id)}
              disabled={status !== 'pending' || isLoading}
              className={cn(
                'w-full flex items-start gap-3 p-4 rounded-lg border-2 transition-all duration-200 text-left',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                isSelected
                  ? 'bg-blue-500/20 border-blue-500 shadow-lg shadow-blue-500/20'
                  : 'bg-gray-800/50 border-gray-700 hover:border-gray-600 hover:bg-gray-800',
                status !== 'pending' && !isSelected && 'opacity-50'
              )}
              data-testid={`option-${option.id}`}
              data-selected={isSelected}
              data-recommended={isRecommended}
              aria-label={`Select ${option.label}`}
            >
              {/* Radio indicator */}
              <div className="flex-shrink-0 mt-0.5">
                {isSelected ? (
                  <CheckCircle2 className="w-5 h-5 text-blue-400" data-testid={`selected-icon-${option.id}`} />
                ) : (
                  <Circle className="w-5 h-5 text-gray-500" data-testid={`unselected-icon-${option.id}`} />
                )}
              </div>

              {/* Option content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={cn(
                      'font-semibold text-sm',
                      isSelected ? 'text-blue-200' : 'text-gray-200'
                    )}
                    data-testid={`option-label-${option.id}`}
                  >
                    {option.label}
                  </span>
                  {isRecommended && (
                    <Badge
                      className="flex items-center gap-1 px-1.5 py-0.5 bg-purple-500/20 text-purple-300 border-purple-500/40"
                      data-testid={`recommended-badge-${option.id}`}
                    >
                      <Sparkles className="w-3 h-3" />
                      <span className="text-xs">Recommended</span>
                    </Badge>
                  )}
                </div>
                {option.description && (
                  <p
                    className={cn(
                      'text-xs',
                      isSelected ? 'text-blue-300' : 'text-gray-400'
                    )}
                    data-testid={`option-description-${option.id}`}
                  >
                    {option.description}
                  </p>
                )}
              </div>
            </button>
          );
        })}
      </div>
    );
  };

  return (
    <Card
      className={cn(
        'bg-gray-900 border-2 transition-all duration-300 shadow-lg',
        statusSettings?.borderColor,
        statusSettings?.bgColor
      )}
      data-testid="decision-card"
      data-status={status}
    >
      <CardHeader className="pb-3">
        {/* Header with question and status badge */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2 flex-1">
            <StatusIcon
              className={cn('w-5 h-5 flex-shrink-0 mt-0.5', statusSettings?.iconColor)}
              data-testid="status-icon"
              aria-label={statusSettings?.label}
            />
            <CardTitle className="text-lg font-semibold text-gray-100" data-testid="decision-question">
              {decisionData.question}
            </CardTitle>
          </div>
          <Badge
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1 border flex-shrink-0',
              statusSettings?.bgColor,
              statusSettings?.color,
              statusSettings?.borderColor
            )}
            data-testid="status-badge"
          >
            <span className="text-xs font-medium">{statusSettings?.label}</span>
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Context (optional) */}
        {decisionData.context && (
          <div
            className="p-3 rounded-lg bg-gray-800/50 border border-gray-700"
            data-testid="context-section"
          >
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1">
              Context
            </p>
            <p className="text-sm text-gray-400" data-testid="context-text">
              {decisionData.context}
            </p>
          </div>
        )}

        {/* Recommendation */}
        {renderRecommendation()}

        {/* Options */}
        {status === 'pending' && renderOptions()}

        {/* Selected option display for decided state */}
        {status === 'decided' && selectedOption && (
          <div
            className="p-4 rounded-lg bg-green-500/10 border border-green-500/40"
            data-testid="selected-decision"
          >
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-2">
              Selected Option
            </p>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-400" />
              <span className="text-sm font-semibold text-green-200" data-testid="decided-option-label">
                {decisionData.options.find(opt => opt.id === selectedOption)?.label || selectedOption}
              </span>
            </div>
          </div>
        )}

        {/* Reasoning input (if pending and reasoningVisible) */}
        {status === 'pending' && decisionData.reasoningVisible && (
          <div className="space-y-2" data-testid="reasoning-section">
            <label
              htmlFor="decision-reasoning"
              className="flex items-center gap-2 text-xs text-gray-500 font-medium uppercase tracking-wide"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Reasoning (Optional)
            </label>
            <Input
              id="decision-reasoning"
              type="text"
              placeholder="Explain your choice..."
              value={reasoning}
              onChange={(e) => setReasoning(e.target.value)}
              className="bg-gray-800 border-gray-700 text-gray-100 placeholder:text-gray-500"
              data-testid="reasoning-input"
              disabled={isLoading}
            />
          </div>
        )}

        {/* Submit button (if pending) */}
        {status === 'pending' && (
          <div className="flex justify-end pt-2" data-testid="submit-section">
            <button
              onClick={handleSubmit}
              disabled={isLoading || !selectedOption}
              className={cn(
                'flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg',
                'bg-blue-600 hover:bg-blue-500 text-white font-medium',
                'transition-all duration-200 hover:shadow-lg hover:shadow-blue-500/20',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900',
                'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-blue-600'
              )}
              data-testid="submit-button"
              aria-label="Submit decision"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" data-testid="loading-spinner" />
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Submit Decision</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Status message for decided/timeout/skipped */}
        {status !== 'pending' && (
          <div
            className={cn(
              'flex items-center gap-2 px-4 py-3 rounded-lg border',
              statusSettings?.bgColor,
              statusSettings?.borderColor
            )}
            data-testid="status-message"
          >
            <StatusIcon className={cn('w-5 h-5', statusSettings?.iconColor)} />
            <span className={cn('font-medium', statusSettings?.color)}>
              {status === 'decided'
                ? 'Decision has been made'
                : status === 'timeout'
                ? 'Decision has timed out'
                : 'Decision was skipped'}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
