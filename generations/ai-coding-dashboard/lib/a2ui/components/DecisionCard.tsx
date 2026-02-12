/**
 * DecisionCard Component
 * Presents options for human decision-making with recommendation
 * Part of A2UI Component Catalog
 */

'use client';

import React, { useState } from 'react';
import { DecisionCardProps } from '../types';
import { HelpCircle, Star, Check, Loader2 } from 'lucide-react';

export const DecisionCard: React.FC<DecisionCardProps> = ({
  decisionId,
  question,
  options,
  recommendation,
  context,
  onSelect,
  selectedOption,
  isPending = true,
  className = '',
}) => {
  const [hoveredOption, setHoveredOption] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSelect = (optionId: string) => {
    if (!isPending || submitting) return;
    setSubmitting(true);
    onSelect?.(optionId);
  };

  return (
    <div
      className={`rounded-lg border-2 border-purple-600 bg-purple-900/30 overflow-hidden ${className}`}
      role="region"
      aria-label={`Decision required: ${question}`}
      data-testid="decision-card"
      data-decision-id={decisionId}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-start gap-3">
          <HelpCircle className="w-6 h-6 text-purple-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <h3 className="text-lg font-semibold text-white">Decision Required</h3>
            <p className="text-sm text-purple-200 mt-1">{question}</p>
          </div>
        </div>
      </div>

      {/* Context */}
      {context && (
        <div className="px-4 pt-3">
          <p className="text-sm text-gray-300 leading-relaxed bg-gray-800/50 border border-gray-700 rounded-md p-3">
            {context}
          </p>
        </div>
      )}

      {/* Options */}
      <div className="p-4 space-y-2" role="radiogroup" aria-label="Decision options">
        {options.map((option) => {
          const isSelected = selectedOption === option.id;
          const isRecommended = option.recommended || recommendation === option.id;
          const isHovered = hoveredOption === option.id;

          return (
            <button
              key={option.id}
              onClick={() => handleSelect(option.id)}
              onMouseEnter={() => setHoveredOption(option.id)}
              onMouseLeave={() => setHoveredOption(null)}
              disabled={!isPending || submitting}
              role="radio"
              aria-checked={isSelected}
              className={`w-full text-left p-3 rounded-lg border-2 transition-all duration-200
                ${isSelected
                  ? 'border-purple-500 bg-purple-800/40'
                  : isHovered
                  ? 'border-gray-500 bg-gray-800/70'
                  : 'border-gray-700 bg-gray-800/30'
                }
                ${isPending && !submitting ? 'cursor-pointer hover:border-gray-500' : 'cursor-default'}
                disabled:opacity-60 disabled:cursor-not-allowed`}
              data-testid={`decision-option-${option.id}`}
            >
              <div className="flex items-start gap-3">
                <div className={`w-5 h-5 rounded-full border-2 flex-shrink-0 mt-0.5 flex items-center justify-center
                  ${isSelected ? 'border-purple-400 bg-purple-500' : 'border-gray-500'}`}
                >
                  {isSelected && <Check className="w-3 h-3 text-white" />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-white">{option.label}</span>
                    {isRecommended && (
                      <span className="flex items-center gap-1 px-2 py-0.5 text-xs font-semibold text-yellow-300 bg-yellow-900/40 border border-yellow-700 rounded-full">
                        <Star className="w-3 h-3" aria-hidden="true" />
                        Recommended
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">{option.description}</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Submission feedback */}
      {submitting && (
        <div className="px-4 pb-4 flex items-center gap-2 text-sm text-purple-300">
          <Loader2 className="w-4 h-4 animate-spin" />
          Submitting decision...
        </div>
      )}

      {!isPending && selectedOption && (
        <div className="p-4 border-t border-gray-700 bg-gray-800/50">
          <span className="text-sm text-gray-400 italic">
            Decision submitted: {options.find(o => o.id === selectedOption)?.label}
          </span>
        </div>
      )}
    </div>
  );
};

DecisionCard.displayName = 'DecisionCard';

export default DecisionCard;
