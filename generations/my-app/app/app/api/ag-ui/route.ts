import { NextRequest } from "next/server";

/**
 * AG-UI Proxy Endpoint
 *
 * This endpoint proxies requests from the frontend CopilotKit client
 * to the Python FastAPI backend running on port 8000.
 *
 * Endpoints proxied:
 * - POST /api/ag-ui -> http://localhost:8000/ag-ui/stream
 *
 * Features:
 * - Streams Server-Sent Events (SSE) from backend to frontend
 * - Handles CORS properly
 * - Forwards headers and request body
 * - Error handling for backend unavailability
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const AG_UI_ENDPOINT = `${BACKEND_URL}/ag-ui/stream`;

/**
 * POST handler for AG-UI stream endpoint
 */
export async function POST(request: NextRequest) {
  try {
    // Get request body
    const body = await request.json();

    // Forward the request to the Python backend
    const response = await fetch(AG_UI_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
    });

    // Check if backend is available
    if (!response.ok) {
      console.error("Backend error:", response.status, response.statusText);
      return new Response(
        JSON.stringify({
          error: "Backend unavailable",
          status: response.status,
          message: response.statusText,
        }),
        {
          status: 502,
          headers: {
            "Content-Type": "application/json",
          },
        }
      );
    }

    // Stream the SSE response back to the client
    return new Response(response.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
      },
    });
  } catch (error) {
    console.error("AG-UI proxy error:", error);

    // Return error response
    return new Response(
      JSON.stringify({
        error: "Failed to connect to backend",
        message: error instanceof Error ? error.message : "Unknown error",
        hint: "Make sure the Python backend is running on port 8000",
      }),
      {
        status: 500,
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
  }
}

/**
 * GET handler for testing the proxy
 */
export async function GET() {
  try {
    // Test backend availability
    const response = await fetch(`${BACKEND_URL}/health`, {
      method: "GET",
    });

    const isHealthy = response.ok;

    return new Response(
      JSON.stringify({
        status: "ok",
        backend: {
          url: BACKEND_URL,
          healthy: isHealthy,
        },
        endpoints: {
          stream: "/api/ag-ui (POST)",
          health: "/api/ag-ui (GET)",
        },
      }),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({
        status: "error",
        backend: {
          url: BACKEND_URL,
          healthy: false,
          error: error instanceof Error ? error.message : "Unknown error",
        },
      }),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
  }
}

/**
 * OPTIONS handler for CORS preflight
 */
export async function OPTIONS() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
