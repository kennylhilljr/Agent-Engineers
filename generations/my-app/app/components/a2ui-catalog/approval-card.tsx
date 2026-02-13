import React from 'react';
import { A2UIProps, ApprovalCardData } from '@/lib/a2ui-types';

/**
 * ApprovalCard - Request approval interface with approve/reject actions
 * Status: Placeholder - Full implementation pending
 */
export function ApprovalCard({ type, data, metadata }: A2UIProps) {
  const approvalData = data as ApprovalCardData;

  return (
    <div className="border rounded-lg p-4 bg-card text-card-foreground">
      <h3 className="text-lg font-semibold mb-2">Component: {type}</h3>
      <div className="text-sm text-muted-foreground mb-2">
        Status: Placeholder Implementation
      </div>
      <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-48">
        {JSON.stringify({ data: approvalData, metadata }, null, 2)}
      </pre>
    </div>
  );
}
