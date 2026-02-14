import React, { useEffect, useState } from 'react';
import { A2UIProps, MilestoneCardData } from '@/lib/a2ui-types';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { CheckCircle2, Calendar, ArrowRight, Sparkles } from 'lucide-react';

/**
 * MilestoneCard - Celebratory card for project milestones
 * Fully implemented A2UI component with celebratory animations and dark theme
 */
export function MilestoneCard({ type, data, metadata }: A2UIProps) {
  const milestoneData = data as MilestoneCardData;
  const [animate, setAnimate] = useState(false);
  const celebrationEnabled = milestoneData.celebrationAnimation !== false;

  // Calculate completion percentage
  const completionPercentage = milestoneData.totalTasks > 0
    ? Math.round((milestoneData.tasksCompleted / milestoneData.totalTasks) * 100)
    : 0;

  // Trigger animation on mount if enabled
  useEffect(() => {
    if (celebrationEnabled) {
      const timer = setTimeout(() => setAnimate(true), 100);
      return () => clearTimeout(timer);
    }
  }, [celebrationEnabled]);

  // Format completion date
  const formattedDate = milestoneData.completionDate
    ? new Date(milestoneData.completionDate).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null;

  return (
    <Card
      className={cn(
        "bg-gradient-to-br from-green-900/40 via-green-800/30 to-gray-900/40",
        "border-green-500/30 text-gray-100",
        "overflow-hidden relative",
        "transition-all duration-500",
        celebrationEnabled && "hover:shadow-2xl hover:shadow-green-500/20"
      )}
      data-testid="milestone-card"
    >
      {/* Animated glow effect */}
      {celebrationEnabled && (
        <div
          className={cn(
            "absolute inset-0 bg-gradient-to-r from-transparent via-green-400/10 to-transparent",
            "transition-opacity duration-1000",
            animate ? "opacity-100 animate-pulse" : "opacity-0"
          )}
          data-testid="glow-effect"
        />
      )}

      {/* Confetti sparkles (CSS-based decorative elements) */}
      {celebrationEnabled && (
        <>
          <div
            className={cn(
              "absolute top-4 right-4 text-yellow-400 transition-all duration-700",
              animate ? "opacity-100 scale-100" : "opacity-0 scale-0"
            )}
            style={{ transitionDelay: '200ms' }}
            data-testid="sparkle-1"
          >
            <Sparkles className="w-4 h-4" />
          </div>
          <div
            className={cn(
              "absolute top-8 right-12 text-green-400 transition-all duration-700",
              animate ? "opacity-100 scale-100" : "opacity-0 scale-0"
            )}
            style={{ transitionDelay: '400ms' }}
            data-testid="sparkle-2"
          >
            <Sparkles className="w-3 h-3" />
          </div>
          <div
            className={cn(
              "absolute bottom-8 left-8 text-blue-400 transition-all duration-700",
              animate ? "opacity-100 scale-100" : "opacity-0 scale-0"
            )}
            style={{ transitionDelay: '600ms' }}
            data-testid="sparkle-3"
          >
            <Sparkles className="w-3 h-3" />
          </div>
        </>
      )}

      <CardHeader className="pb-3 relative z-10">
        <div className="flex items-start justify-between gap-3">
          {/* Large checkmark icon with animation */}
          <div
            className={cn(
              "flex-shrink-0 transition-all duration-700",
              celebrationEnabled && animate
                ? "scale-100 rotate-0"
                : celebrationEnabled
                ? "scale-0 -rotate-180"
                : "scale-100 rotate-0"
            )}
            data-testid="check-icon-container"
          >
            <div
              className={cn(
                "relative",
                celebrationEnabled && "animate-bounce-slow"
              )}
            >
              <CheckCircle2
                className="w-12 h-12 text-green-400 drop-shadow-lg"
                data-testid="check-icon"
              />
              {/* Glow ring */}
              {celebrationEnabled && (
                <div
                  className={cn(
                    "absolute inset-0 rounded-full bg-green-400/20 blur-xl",
                    "transition-opacity duration-1000",
                    animate ? "opacity-100 animate-pulse" : "opacity-0"
                  )}
                  data-testid="icon-glow"
                />
              )}
            </div>
          </div>

          <div className="flex-1">
            <CardTitle
              className={cn(
                "text-2xl font-bold text-green-100 mb-2",
                "transition-all duration-500",
                celebrationEnabled && animate ? "opacity-100 translate-y-0" : "opacity-90"
              )}
              data-testid="milestone-title"
            >
              {milestoneData.title || 'Milestone Reached!'}
            </CardTitle>

            {/* Summary */}
            <p
              className="text-sm text-gray-300 leading-relaxed"
              data-testid="milestone-summary"
            >
              {milestoneData.summary || 'Milestone completed successfully.'}
            </p>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 relative z-10">
        {/* Tasks Completed Counter */}
        <div
          className="bg-gray-800/50 rounded-lg p-4 border border-green-500/20"
          data-testid="tasks-counter"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-300">Tasks Completed</span>
            <Badge
              className="bg-green-500/20 text-green-400 border-green-500/30 px-3 py-1"
              data-testid="completion-badge"
            >
              {milestoneData.tasksCompleted} / {milestoneData.totalTasks}
            </Badge>
          </div>

          {/* Progress Bar */}
          <div className="space-y-2" data-testid="progress-section">
            <div className="flex items-center justify-between text-xs text-gray-400">
              <span>Progress</span>
              <span
                className="font-semibold text-green-400"
                data-testid="completion-percentage"
              >
                {completionPercentage}%
              </span>
            </div>
            <Progress
              value={completionPercentage}
              className={cn(
                "h-3 bg-gray-700",
                celebrationEnabled && "transition-all duration-1000"
              )}
              data-testid="progress-bar"
            />
          </div>
        </div>

        {/* Celebration Message */}
        {milestoneData.celebrationMessage && (
          <div
            className={cn(
              "bg-green-500/10 border border-green-500/30 rounded-lg p-4",
              "transition-all duration-700",
              celebrationEnabled && animate
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-2"
            )}
            data-testid="celebration-message"
          >
            <p className="text-sm text-green-200 italic">
              "{milestoneData.celebrationMessage}"
            </p>
          </div>
        )}

        {/* Completion Date */}
        {formattedDate && (
          <div
            className="flex items-center gap-2 text-sm text-gray-400"
            data-testid="completion-date"
          >
            <Calendar className="w-4 h-4" />
            <span>Completed on {formattedDate}</span>
          </div>
        )}

        {/* Next Phase Preview */}
        {milestoneData.nextPhase && (
          <div
            className={cn(
              "bg-blue-500/10 border border-blue-500/30 rounded-lg p-4",
              "flex items-center gap-3",
              "transition-all duration-700",
              celebrationEnabled && animate
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-2"
            )}
            data-testid="next-phase"
            style={{ transitionDelay: celebrationEnabled ? '200ms' : '0ms' }}
          >
            <ArrowRight className="w-5 h-5 text-blue-400 flex-shrink-0" />
            <div>
              <p className="text-xs font-medium text-blue-300 mb-1">Up Next</p>
              <p className="text-sm text-gray-200">{milestoneData.nextPhase}</p>
            </div>
          </div>
        )}
      </CardContent>

      <style jsx>{`
        @keyframes bounce-slow {
          0%, 100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-10px);
          }
        }
        .animate-bounce-slow {
          animation: bounce-slow 2s ease-in-out infinite;
        }
      `}</style>
    </Card>
  );
}
