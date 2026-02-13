"use client";

import React, { ReactNode } from "react";

/**
 * CopilotKit Provider Component
 *
 * This component wraps the application with CopilotKit context
 * and configures the AG-UI connection to the Python backend.
 *
 * Configuration:
 * - Runtime URL: /api/ag-ui (proxies to http://localhost:8000/ag-ui/stream)
 * - Theme: Dark mode
 * - SSE: Server-Sent Events for real-time updates
 */

interface CopilotProviderProps {
  children: ReactNode;
}

export function CopilotProvider({ children }: CopilotProviderProps) {
  // Note: CopilotKit packages would be imported here in production
  // For now, this is a placeholder that will be updated once CopilotKit is accessible

  // TODO: Once @copilotkit/react-core is available, implement:
  // import { CopilotKit } from "@copilotkit/react-core";
  // import { CopilotSidebar } from "@copilotkit/react-ui";

  // Configuration that will be used:
  const runtimeUrl = "/api/ag-ui";

  // Mock implementation until CopilotKit is installed
  return (
    <div data-copilot-provider="true" data-runtime-url={runtimeUrl}>
      {children}
    </div>
  );

  // Production implementation (when CopilotKit is available):
  /*
  return (
    <CopilotKit
      runtimeUrl={runtimeUrl}
      transcribeAudioUrl="/api/transcribe"
      publicApiKey={undefined} // Using proxy, no public key needed
      showDevConsole={process.env.NODE_ENV === 'development'}
    >
      {children}
    </CopilotKit>
  );
  */
}

/**
 * Hook to access CopilotKit runtime
 * This will be used by components to interact with the agent
 */
export function useCopilotRuntime() {
  // Mock implementation
  return {
    isConnected: false,
    sendMessage: async (message: string) => {
      console.log("CopilotKit sendMessage:", message);
    },
  };

  // Production implementation:
  /*
  import { useCopilotContext } from "@copilotkit/react-core";
  return useCopilotContext();
  */
}
