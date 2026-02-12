/**
 * ApprovalCard Component
 * Human-in-the-loop approval for risky agent actions
 * Part of A2UI Component Catalog
 */

'use client';

import React, { useState } from 'react';
import { ApprovalCardProps, RiskLevel } from '../types';
import { ShieldAlert, ShieldCheck, AlertTriangle, Info, Loader2 } from 'lucide-react';

const riskConfig: Record<RiskLevel, {
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
}> = {
  low: {
    icon: Info,
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/30',
    borderColor: 'border-blue-600',
    label: 'Low Risk',
  },
  medium: {
    icon: AlertTriangle,
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/30',
    borderColor: 'border-yellow-600',
    label: 'Medium Risk',
  },
  high: {
    icon: ShieldAlert,
    color: 'text-orange-400',
    bgColor: 'bg-orange-900/30',
    borderColor: 'border-orange-600',
    label: 'High Risk',
  },
  critical: {
    icon: ShieldAlert,
    color: 'text-red-400',
    bgColor: 'bg-red-900/30',
    borderColor: 'border-red-600',
    label: 'Critical Risk',
  },
};

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  approvalId,
  action,
  riskLevel,
  context,
  affectedFiles,
  estimatedImpact,
  onApprove,
  onReject,
  isPending = true,
  className = '',
}) => {
  const [submitting, setSubmitting] = useState<'approve' | 'reject' | null>(null);
  const config = riskConfig[riskLevel];
  const RiskIcon = config.icon;

  const handleApprove = () => {
    setSubmitting('approve');
    onApprove?.();
  };

  const handleReject = () => {
    setSubmitting('reject');
    onReject?.();
  };

  return (
    <div
      className={`rounded-lg border-2 ${config.borderColor} ${config.bgColor} overflow-hidden ${className}`}
      role="alert"
      aria-label={`Approval required: ${action}`}
      data-testid="approval-card"
      data-approval-id={approvalId}
      data-risk-level={riskLevel}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <RiskIcon className={`w-6 h-6 ${config.color} flex-shrink-0 mt-0.5`} aria-hidden="true" />
            <div>
              <h3 className="text-lg font-semibold text-white">Approval Required</h3>
              <span className={`inline-block mt-1 px-2 py-0.5 text-xs font-semibold rounded-full ${config.color} bg-gray-800 border ${config.borderColor}`}>
                {config.label}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        <div>
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Action
          </h4>
          <p className="text-sm text-white font-medium">{action}</p>
        </div>

        <div>
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Context
          </h4>
          <p className="text-sm text-gray-300 leading-relaxed">{context}</p>
        </div>

        {estimatedImpact && (
          <div>
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
              Estimated Impact
            </h4>
            <p className="text-sm text-gray-300">{estimatedImpact}</p>
          </div>
        )}

        {affectedFiles && affectedFiles.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
              Affected Files ({affectedFiles.length})
            </h4>
            <ul className="space-y-1" role="list">
              {affectedFiles.map((file) => (
                <li key={file} className="text-sm text-gray-300 font-mono bg-gray-800/50 px-2 py-1 rounded">
                  {file}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Actions */}
      {isPending && (
        <div className="p-4 border-t border-gray-700 bg-gray-800/50 flex items-center gap-3">
          <button
            onClick={handleApprove}
            disabled={submitting !== null}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
              bg-green-600 hover:bg-green-700 text-white font-semibold text-sm
              transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Approve action"
          >
            {submitting === 'approve' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ShieldCheck className="w-4 h-4" />
            )}
            Approve
          </button>
          <button
            onClick={handleReject}
            disabled={submitting !== null}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
              bg-red-600 hover:bg-red-700 text-white font-semibold text-sm
              transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Reject action"
          >
            {submitting === 'reject' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ShieldAlert className="w-4 h-4" />
            )}
            Reject
          </button>
        </div>
      )}

      {!isPending && (
        <div className="p-4 border-t border-gray-700 bg-gray-800/50">
          <span className="text-sm text-gray-400 italic">Decision submitted</span>
        </div>
      )}
    </div>
  );
};

ApprovalCard.displayName = 'ApprovalCard';

export default ApprovalCard;
