"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { ReactNode, Component, ErrorInfo, useState, useEffect } from "react";

interface CopilotKitProviderProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

/**
 * Error boundary component that catches CopilotKit errors and allows the app to render
 */
class CopilotKitErrorBoundary extends Component<
  { children: ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    // Check if it's the specific AG-UI connection error
    const isAgUiError =
      error.message.includes("Agent 'default' not found") ||
      error.message.includes("useAgent") ||
      error.message.includes("runtime sync");

    if (isAgUiError) {
      // Suppress console error for AG-UI connection issues
      if (typeof window !== "undefined") {
        console.warn(
          "[CopilotKit] AG-UI backend not available - running in fallback mode"
        );
      }
      return { hasError: true, error };
    }

    // For non-AG-UI errors, still return error state but mark it differently
    return { hasError: false, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Only log AG-UI connection errors as warnings
    const isAgUiError =
      error.message.includes("Agent 'default' not found") ||
      error.message.includes("useAgent") ||
      error.message.includes("runtime sync");

    if (isAgUiError) {
      console.warn(
        "[CopilotKit] Running without AG-UI backend:",
        error.message
      );
    } else {
      // Re-throw non-AG-UI errors
      console.error("[CopilotKit] Unexpected error:", error, errorInfo);
      throw error;
    }
  }

  render() {
    if (this.state.hasError) {
      // Render children without CopilotKit when there's an AG-UI connection error
      return this.props.children;
    }

    return this.props.children;
  }
}

/**
 * Safe wrapper component that handles CopilotKit initialization errors
 */
function SafeCopilotKit({ children }: { children: ReactNode }) {
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    // Set up error handler for unhandled promise rejections
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const isAgUiError =
        event.reason?.message?.includes("Agent 'default' not found") ||
        event.reason?.message?.includes("useAgent") ||
        event.reason?.message?.includes("runtime sync");

      if (isAgUiError) {
        event.preventDefault();
        console.warn(
          "[CopilotKit] AG-UI connection error suppressed:",
          event.reason?.message
        );
        setHasError(true);
      }
    };

    window.addEventListener("unhandledrejection", handleUnhandledRejection);
    return () => {
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, []);

  if (hasError) {
    return <>{children}</>;
  }

  return (
    <CopilotKit
      runtimeUrl="/api/ag-ui"
      headers={{
        "Content-Type": "application/json",
      }}
      showDevConsole={process.env.NODE_ENV === "development"}
    >
      {children}
    </CopilotKit>
  );
}

/**
 * CopilotKit provider component that wraps the app and connects to AG-UI runtime
 *
 * This component:
 * - Configures CopilotKit with the AG-UI runtime URL
 * - Provides the CopilotKit context to all child components
 * - Handles connection to the Python backend through the proxy API route
 * - Gracefully degrades when AG-UI backend is not available
 */
export function CopilotKitProvider({ children }: CopilotKitProviderProps) {
  // Check if AG-UI should be enabled (can be disabled via env var)
  const agUiEnabled = process.env.NEXT_PUBLIC_ENABLE_AG_UI !== "false";

  if (!agUiEnabled) {
    console.info("[CopilotKit] AG-UI disabled via environment variable");
    return <>{children}</>;
  }

  return (
    <CopilotKitErrorBoundary>
      <SafeCopilotKit>{children}</SafeCopilotKit>
    </CopilotKitErrorBoundary>
  );
}
