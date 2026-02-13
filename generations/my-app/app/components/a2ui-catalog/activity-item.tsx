import React from 'react';
import { A2UIProps, ActivityItemData } from '@/lib/a2ui-types';

/**
 * ActivityItem - Displays a single activity/event in a timeline
 * Status: Placeholder - Full implementation pending
 */
export function ActivityItem({ type, data, metadata }: A2UIProps) {
  const activityData = data as ActivityItemData;

  return (
    <div className="border rounded-lg p-4 bg-card text-card-foreground">
      <h3 className="text-lg font-semibold mb-2">Component: {type}</h3>
      <div className="text-sm text-muted-foreground mb-2">
        Status: Placeholder Implementation
      </div>
      <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-48">
        {JSON.stringify({ data: activityData, metadata }, null, 2)}
      </pre>
    </div>
  );
}
