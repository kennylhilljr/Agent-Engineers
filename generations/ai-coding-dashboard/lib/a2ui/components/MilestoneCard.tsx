/**
 * MilestoneCard Component
 * Displays milestone achievements with celebratory styling
 * Part of A2UI Component Catalog
 */

'use client';

import React from 'react';
import { MilestoneCardProps } from '../types';
import { Trophy, ArrowRight, CheckCircle } from 'lucide-react';

export const MilestoneCard: React.FC<MilestoneCardProps> = ({
  title,
  summary,
  tasksCompleted,
  nextPhase,
  achievements,
  timestamp,
  className = '',
}) => {
  const formatTimestamp = (ts?: string): string => {
    if (!ts) return '';
    try {
      return new Date(ts).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  return (
    <div
      className={`rounded-lg border-2 border-green-500 bg-gradient-to-br from-green-900/40 to-green-800/20
        overflow-hidden relative ${className}`}
      role="article"
      aria-label={`Milestone: ${title}`}
      data-testid="milestone-card"
    >
      {/* Glow effect */}
      <div className="absolute inset-0 bg-green-500/5 pointer-events-none" />

      {/* Header */}
      <div className="p-4 border-b border-green-800/50 relative">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-full bg-green-800/50 border border-green-600">
            <Trophy className="w-6 h-6 text-green-400" aria-hidden="true" />
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-bold text-green-300">{title}</h3>
            {timestamp && (
              <span className="text-xs text-green-400/70 mt-1 block">
                {formatTimestamp(timestamp)}
              </span>
            )}
          </div>
          <div className="px-3 py-1 rounded-full text-xs font-bold text-green-300 bg-green-800/50 border border-green-600">
            {tasksCompleted} tasks done
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4 relative">
        <p className="text-sm text-green-100 leading-relaxed">{summary}</p>

        {/* Achievements */}
        {achievements && achievements.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-green-400/80 uppercase tracking-wide">
              Achievements
            </h4>
            <ul className="space-y-1.5" role="list">
              {achievements.map((achievement, index) => (
                <li key={index} className="flex items-start gap-2 text-sm text-green-200">
                  <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
                  <span>{achievement}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Next Phase */}
        {nextPhase && (
          <div className="flex items-center gap-2 p-3 bg-gray-800/50 border border-green-800/50 rounded-lg">
            <ArrowRight className="w-4 h-4 text-blue-400 flex-shrink-0" aria-hidden="true" />
            <div>
              <span className="text-xs text-gray-400 block">Next Phase</span>
              <span className="text-sm text-white font-medium">{nextPhase}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

MilestoneCard.displayName = 'MilestoneCard';

export default MilestoneCard;
