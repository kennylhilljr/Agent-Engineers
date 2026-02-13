import React from 'react';
import { A2UIProps, MilestoneCardData } from '@/lib/a2ui-types';

/**
 * MilestoneCard - Display project milestone with progress and status
 * Status: Placeholder - Full implementation pending
 */
export function MilestoneCard({ type, data, metadata }: A2UIProps) {
  const milestoneData = data as MilestoneCardData;

  return (
    <div className="border rounded-lg p-4 bg-card text-card-foreground">
      <h3 className="text-lg font-semibold mb-2">Component: {type}</h3>
      <div className="text-sm text-muted-foreground mb-2">
        Status: Placeholder Implementation
      </div>
      <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-48">
        {JSON.stringify({ data: milestoneData, metadata }, null, 2)}
      </pre>
    </div>
  );
}
