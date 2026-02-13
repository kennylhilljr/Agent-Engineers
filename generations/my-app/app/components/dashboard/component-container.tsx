"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Sparkles, AlertTriangle } from "lucide-react";

interface ComponentContainerProps {
  components?: React.ReactNode[];
  isLoading?: boolean;
  error?: string | null;
}

export function ComponentContainer({
  components = [],
  isLoading = false,
  error = null,
}: ComponentContainerProps) {
  // Error state
  if (error) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="w-5 h-5" />
            Error Loading Components
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">{error}</p>
        </CardContent>
      </Card>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <Card className="w-full">
        <CardContent className="flex flex-col items-center justify-center py-16">
          <Loader2 className="w-12 h-12 text-primary animate-spin mb-4" />
          <p className="text-muted-foreground text-center">
            Agent is generating components...
          </p>
        </CardContent>
      </Card>
    );
  }

  // Empty state
  if (components.length === 0) {
    return (
      <Card className="w-full">
        <CardContent className="flex flex-col items-center justify-center py-16">
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-4">
            <Sparkles className="w-8 h-8 text-primary" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Ready for AI Generation</h3>
          <p className="text-muted-foreground text-center max-w-md">
            Waiting for agent to generate components... Use the chat to request new UI components
            and they'll appear here.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Render components in responsive grid
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 w-full">
      {components.map((component, index) => (
        <div key={index} className="w-full">
          {component}
        </div>
      ))}
    </div>
  );
}
