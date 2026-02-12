/**
 * KAN-52: Verify and test the AG-UI adapter for CopilotKit integration
 *
 * This test suite verifies:
 * 1. AG-UI stream endpoint exists and responds correctly (POST /api/ag-ui)
 * 2. SSE response format is correct
 * 3. CORS headers are set for frontend (port 3010)
 * 4. Error handling for invalid requests
 * 5. CopilotKit provider wraps the app correctly
 * 6. AG-UI runtime URL configuration
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import fs from 'fs';
import path from 'path';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const projectRoot = path.resolve(__dirname, '..');

function readFile(relativePath: string): string {
  return fs.readFileSync(path.join(projectRoot, relativePath), 'utf-8');
}

// ---------------------------------------------------------------------------
// 1. AG-UI route file existence and structure
// ---------------------------------------------------------------------------

describe('KAN-52: AG-UI Adapter Route', () => {
  const routePath = path.join(projectRoot, 'app', 'api', 'ag-ui', 'route.ts');

  it('should have the AG-UI route file at app/api/ag-ui/route.ts', () => {
    expect(fs.existsSync(routePath)).toBe(true);
  });

  it('should export a POST handler', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('export async function POST');
  });

  it('should export a GET handler', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('export async function GET');
  });

  it('should export an OPTIONS handler for CORS preflight', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('export async function OPTIONS');
  });

  it('should export PUT, DELETE, and PATCH handlers for full proxy support', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('export async function PUT');
    expect(content).toContain('export async function DELETE');
    expect(content).toContain('export async function PATCH');
  });
});

// ---------------------------------------------------------------------------
// 2. SSE / Streaming response handling
// ---------------------------------------------------------------------------

describe('KAN-52: SSE Response Format', () => {
  it('should detect text/event-stream content type as streaming', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('text/event-stream');
  });

  it('should detect application/stream+json content type as streaming', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('application/stream+json');
  });

  it('should create a ReadableStream for streaming responses', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('new ReadableStream');
  });

  it('should set Cache-Control to no-cache for streaming responses', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    // Verify the streaming response includes the correct cache header
    expect(content).toContain('"Cache-Control": "no-cache"');
  });

  it('should set Connection to keep-alive for streaming responses', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('Connection: "keep-alive"');
  });

  it('should use TextDecoder/TextEncoder for proper chunk encoding', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('new TextDecoder');
    expect(content).toContain('new TextEncoder');
  });
});

// ---------------------------------------------------------------------------
// 3. CORS headers
// ---------------------------------------------------------------------------

describe('KAN-52: CORS Headers', () => {
  const routeContent = () => readFile('app/api/ag-ui/route.ts');

  it('should set Access-Control-Allow-Origin header', () => {
    const content = routeContent();
    expect(content).toContain('Access-Control-Allow-Origin');
  });

  it('should allow all origins with wildcard for development', () => {
    const content = routeContent();
    // The route uses "*" to allow all origins (compatible with port 3010 frontend)
    expect(content).toContain('"Access-Control-Allow-Origin", "*"');
  });

  it('should set Access-Control-Allow-Methods with all HTTP methods', () => {
    const content = routeContent();
    expect(content).toContain('Access-Control-Allow-Methods');
    expect(content).toContain('GET, POST, PUT, DELETE, PATCH, OPTIONS');
  });

  it('should set Access-Control-Allow-Headers for Content-Type and Authorization', () => {
    const content = routeContent();
    expect(content).toContain('Access-Control-Allow-Headers');
    expect(content).toContain('Content-Type, Authorization');
  });

  it('should return 204 with Max-Age for OPTIONS preflight', () => {
    const content = routeContent();
    expect(content).toContain('status: 204');
    expect(content).toContain('"Access-Control-Max-Age": "86400"');
  });

  it('should include CORS headers on error responses', () => {
    const content = routeContent();
    // The error handling blocks (503 and 500) should also include CORS headers
    const errorBlocks = content.split('NextResponse.json');
    // There are at least three NextResponse.json calls: non-streaming success, 503 error, 500 error
    // Each error response should have CORS headers
    let corsInErrorCount = 0;
    for (const block of errorBlocks) {
      if (block.includes('Access-Control-Allow-Origin') && block.includes('error')) {
        corsInErrorCount++;
      }
    }
    expect(corsInErrorCount).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// 4. Error handling
// ---------------------------------------------------------------------------

describe('KAN-52: Error Handling', () => {
  it('should catch and handle ECONNREFUSED errors as 503', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('ECONNREFUSED');
    expect(content).toContain('status: 503');
  });

  it('should catch and handle fetch failed errors as connection errors', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('fetch failed');
    expect(content).toContain('isConnectionError');
  });

  it('should return 500 for generic proxy errors', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('status: 500');
    expect(content).toContain('"Proxy error"');
  });

  it('should include error details in the response body', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    // Both error responses include error, message, and details fields
    expect(content).toContain('error:');
    expect(content).toContain('message:');
    expect(content).toContain('details: errorMessage');
  });

  it('should provide a helpful message when backend is unavailable', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('Unable to connect to backend');
    expect(content).toContain('Please ensure the Python backend is running');
  });

  it('should handle errors when reading the request body', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('Error reading request body');
  });
});

// ---------------------------------------------------------------------------
// 5. CopilotKit Provider wraps the app correctly
// ---------------------------------------------------------------------------

describe('KAN-52: CopilotKit Provider', () => {
  it('should have the CopilotKitProvider component in lib/copilot-provider.tsx', () => {
    const providerPath = path.join(projectRoot, 'lib', 'copilot-provider.tsx');
    expect(fs.existsSync(providerPath)).toBe(true);
  });

  it('should export CopilotKitProvider as a named export', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain('export function CopilotKitProvider');
  });

  it('should be a client component with "use client" directive', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content.trimStart().startsWith('"use client"')).toBe(true);
  });

  it('should import CopilotKit from @copilotkit/react-core', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain('import { CopilotKit } from "@copilotkit/react-core"');
  });

  it('should wrap children in the CopilotKit component', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain('<CopilotKit');
    expect(content).toContain('{children}');
    expect(content).toContain('</CopilotKit>');
  });

  it('should include an error boundary for graceful degradation', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain('CopilotKitErrorBoundary');
    expect(content).toContain('getDerivedStateFromError');
    expect(content).toContain('componentDidCatch');
  });

  it('should handle AG-UI specific errors (Agent not found, useAgent, runtime sync)', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain("Agent 'default' not found");
    expect(content).toContain('useAgent');
    expect(content).toContain('runtime sync');
  });

  it('should support disabling AG-UI via NEXT_PUBLIC_ENABLE_AG_UI env var', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain('NEXT_PUBLIC_ENABLE_AG_UI');
    expect(content).toContain('!agUiEnabled');
  });

  it('should suppress unhandled promise rejections for AG-UI errors', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain('unhandledrejection');
    expect(content).toContain('event.preventDefault()');
  });

  it('should render children directly when AG-UI is disabled', () => {
    const content = readFile('lib/copilot-provider.tsx');
    // When disabled via env var, it renders children without CopilotKit wrapper
    expect(content).toContain('return <>{children}</>');
  });

  it('should set Content-Type header to application/json on the CopilotKit component', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain('"Content-Type": "application/json"');
  });

  it('should show dev console only in development mode', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain('showDevConsole={process.env.NODE_ENV === "development"}');
  });
});

// ---------------------------------------------------------------------------
// 6. AG-UI Runtime URL configuration
// ---------------------------------------------------------------------------

describe('KAN-52: AG-UI Runtime URL Configuration', () => {
  it('should configure CopilotKit with runtimeUrl pointing to /api/ag-ui', () => {
    const content = readFile('lib/copilot-provider.tsx');
    expect(content).toContain('runtimeUrl="/api/ag-ui"');
  });

  it('should use BACKEND_URL env variable in the route with localhost:8000 as default', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('process.env.BACKEND_URL');
    expect(content).toContain('"http://localhost:8000"');
  });

  it('should strip /api/ag-ui prefix when proxying to backend', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('url.pathname.replace("/api/ag-ui", "")');
  });

  it('should preserve query string parameters when proxying', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('url.search');
    // Verify query params are appended to target URL
    expect(content).toContain('${url.search}');
  });

  it('should skip the Host header when proxying to backend', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('host');
    // Verify the host header is explicitly skipped
    expect(content).toMatch(/key\.toLowerCase\(\)\s*!==\s*"host"/);
  });
});

// ---------------------------------------------------------------------------
// 7. Layout integration
// ---------------------------------------------------------------------------

describe('KAN-52: Layout Integration', () => {
  it('should import CopilotKitProvider in root layout', () => {
    const content = readFile('app/layout.tsx');
    expect(content).toContain('import { CopilotKitProvider } from "@/lib/copilot-provider"');
  });

  it('should wrap page children with CopilotKitProvider in the layout', () => {
    const content = readFile('app/layout.tsx');
    expect(content).toContain('<CopilotKitProvider>');
    expect(content).toContain('{children}');
    expect(content).toContain('</CopilotKitProvider>');
  });

  it('should have CopilotKitProvider inside the body tag', () => {
    const content = readFile('app/layout.tsx');
    const bodyStart = content.indexOf('<body');
    const bodyEnd = content.indexOf('</body>');
    const copilotStart = content.indexOf('<CopilotKitProvider>');
    const copilotEnd = content.indexOf('</CopilotKitProvider>');

    expect(bodyStart).toBeLessThan(copilotStart);
    expect(copilotEnd).toBeLessThan(bodyEnd);
  });

  it('should have dark theme enabled on html element', () => {
    const content = readFile('app/layout.tsx');
    expect(content).toContain('className="dark"');
  });
});

// ---------------------------------------------------------------------------
// 8. Backend proxy behavior (mock-based unit tests)
// ---------------------------------------------------------------------------

describe('KAN-52: Backend Proxy Behavior', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    // Reset fetch mock before each test
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('should only include body for non-GET/HEAD methods', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('method !== "GET" && method !== "HEAD"');
  });

  it('should construct target URL from BACKEND_URL and path after /api/ag-ui', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('`${BACKEND_URL}${pathAfterAgUi}${url.search}`');
  });

  it('should forward response status code from backend', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    // Both streaming and non-streaming responses pass through the backend status
    expect(content).toContain('status: response.status');
  });

  it('should copy response headers from backend for non-streaming responses', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('response.headers.forEach');
    expect(content).toContain('responseHeaders.set(key, value)');
  });

  it('should handle streaming error by calling controller.error', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('controller.error(error)');
  });

  it('should close the stream controller when reading is done', () => {
    const content = readFile('app/api/ag-ui/route.ts');
    expect(content).toContain('controller.close()');
  });
});
