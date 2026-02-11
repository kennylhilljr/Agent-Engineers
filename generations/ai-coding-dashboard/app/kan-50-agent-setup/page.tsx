"use client";

import { CheckCircle2, Circle, Terminal, FileText, FolderTree, Package } from "lucide-react";

export default function KAN50AgentSetupPage() {
  const setupSteps = [
    {
      title: "Create Virtual Environment",
      command: "python3 -m venv venv",
      description: "Initialize Python virtual environment",
    },
    {
      title: "Activate Environment",
      command: "source venv/bin/activate",
      description: "Activate the virtual environment (Windows: venv\\Scripts\\activate)",
    },
    {
      title: "Install Dependencies",
      command: "pip install -r requirements.txt",
      description: "Install all required packages",
    },
    {
      title: "Configure Environment",
      command: "cp .env.example .env",
      description: "Copy environment template and configure",
    },
    {
      title: "Run Tests",
      command: "pytest test_agent_setup.py -v",
      description: "Verify setup with comprehensive test suite",
    },
    {
      title: "Start Server",
      command: "python main.py",
      description: "Launch the FastAPI development server",
    },
  ];

  const fileStructure = [
    { name: "agent/", icon: FolderTree, description: "Backend root directory" },
    { name: "├── __init__.py", icon: FileText, description: "Python package initialization" },
    { name: "├── main.py", icon: FileText, description: "FastAPI application" },
    { name: "├── requirements.txt", icon: Package, description: "Python dependencies" },
    { name: "├── .env.example", icon: FileText, description: "Environment template" },
    { name: "├── .gitignore", icon: FileText, description: "Git ignore rules" },
    { name: "├── README.md", icon: FileText, description: "Backend documentation" },
    { name: "├── test_agent_setup.py", icon: FileText, description: "Comprehensive tests (43 tests)" },
    { name: "└── validate_setup.py", icon: FileText, description: "Setup validation script" },
  ];

  const features = [
    {
      title: "FastAPI Application",
      items: [
        "Modern async Python web framework",
        "Auto-generated OpenAPI docs at /docs",
        "Pydantic validation for all requests/responses",
        "CORS middleware for frontend integration",
      ],
    },
    {
      title: "Endpoints",
      items: [
        "GET /health - Health check with version info",
        "GET / - API metadata and endpoint list",
        "POST /ag-ui/stream - Placeholder for AG-UI protocol (KAN-52+)",
      ],
    },
    {
      title: "Dependencies",
      items: [
        "pydantic-ai - AI agent framework",
        "fastapi - Web framework",
        "uvicorn - ASGI server",
        "python-dotenv - Environment management",
      ],
    },
    {
      title: "Testing",
      items: [
        "43 comprehensive tests",
        "Directory structure validation",
        "Requirements verification",
        "FastAPI app functionality tests",
        "CORS configuration tests",
      ],
    },
  ];

  const endpoints = [
    {
      method: "GET",
      path: "/health",
      description: "Health check endpoint",
      response: {
        status: "healthy",
        message: "AI Agent Backend is running",
        version: "0.1.0",
        environment: "development",
      },
    },
    {
      method: "GET",
      path: "/",
      description: "API information",
      response: {
        name: "AI Coding Dashboard Agent",
        version: "0.1.0",
        status: "operational",
      },
    },
    {
      method: "POST",
      path: "/ag-ui/stream",
      description: "AG-UI protocol streaming (placeholder)",
      response: {
        error: "Not Implemented",
        message: "Will be implemented in KAN-52+",
      },
    },
  ];

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <Terminal className="w-8 h-8 text-blue-600" />
          <h1 className="text-4xl font-bold">KAN-50: Python Agent Backend</h1>
        </div>
        <p className="text-lg text-gray-600 dark:text-gray-300">
          Pydantic AI agent backend initialized with FastAPI, comprehensive tests, and AG-UI protocol foundation
        </p>
      </div>

      {/* Validation Status */}
      <div className="mb-8 p-6 bg-green-50 dark:bg-green-900/20 border-2 border-green-500 rounded-lg">
        <div className="flex items-center gap-3 mb-3">
          <CheckCircle2 className="w-6 h-6 text-green-600" />
          <h2 className="text-xl font-bold text-green-800 dark:text-green-300">
            All Validation Checks Passed
          </h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            <span>File Structure</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            <span>Requirements.txt</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            <span>Main.py Components</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            <span>.env.example</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            <span>.gitignore</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            <span>Test File (43 tests)</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            <span>Python Syntax</span>
          </div>
        </div>
      </div>

      {/* File Structure */}
      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4">File Structure</h2>
        <div className="bg-gray-50 dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="font-mono text-sm space-y-2">
            {fileStructure.map((file, index) => {
              const Icon = file.icon;
              return (
                <div key={index} className="flex items-center gap-3 group hover:bg-gray-100 dark:hover:bg-gray-700 p-2 rounded">
                  <Icon className="w-4 h-4 text-blue-600" />
                  <span className="font-semibold">{file.name}</span>
                  <span className="text-gray-500 dark:text-gray-400 ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
                    {file.description}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Setup Instructions */}
      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4">Setup Instructions</h2>
        <div className="space-y-4">
          {setupSteps.map((step, index) => (
            <div
              key={index}
              className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4"
            >
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 rounded-full flex items-center justify-center font-bold">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold mb-2">{step.title}</h3>
                  <code className="block bg-gray-100 dark:bg-gray-900 px-4 py-2 rounded text-sm mb-2 overflow-x-auto">
                    {step.command}
                  </code>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{step.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Features Grid */}
      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4">Features & Capabilities</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {features.map((feature, index) => (
            <div
              key={index}
              className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6"
            >
              <h3 className="font-semibold text-lg mb-3">{feature.title}</h3>
              <ul className="space-y-2">
                {feature.items.map((item, itemIndex) => (
                  <li key={itemIndex} className="flex items-start gap-2 text-sm">
                    <Circle className="w-2 h-2 mt-1.5 fill-current text-blue-600" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* API Endpoints */}
      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4">API Endpoints</h2>
        <div className="space-y-4">
          {endpoints.map((endpoint, index) => (
            <div
              key={index}
              className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4"
            >
              <div className="flex items-center gap-3 mb-3">
                <span
                  className={`px-3 py-1 text-xs font-bold rounded ${
                    endpoint.method === "GET"
                      ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                      : "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300"
                  }`}
                >
                  {endpoint.method}
                </span>
                <code className="font-mono font-semibold">{endpoint.path}</code>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{endpoint.description}</p>
              <div className="bg-gray-50 dark:bg-gray-900 p-3 rounded overflow-x-auto">
                <pre className="text-xs">{JSON.stringify(endpoint.response, null, 2)}</pre>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Next Steps */}
      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4">Next Steps</h2>
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
          <ul className="space-y-3">
            <li className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5" />
              <div>
                <strong>KAN-50 Complete:</strong> Backend foundation with FastAPI, Pydantic AI, and comprehensive tests
              </div>
            </li>
            <li className="flex items-start gap-3">
              <Circle className="w-5 h-5 text-gray-400 mt-0.5" />
              <div>
                <strong>KAN-52+:</strong> Implement Pydantic AI agent with model integration
              </div>
            </li>
            <li className="flex items-start gap-3">
              <Circle className="w-5 h-5 text-gray-400 mt-0.5" />
              <div>
                <strong>Future:</strong> AG-UI protocol streaming for CopilotKit frontend integration
              </div>
            </li>
            <li className="flex items-start gap-3">
              <Circle className="w-5 h-5 text-gray-400 mt-0.5" />
              <div>
                <strong>Future:</strong> Database integration, authentication, and production deployment
              </div>
            </li>
          </ul>
        </div>
      </section>

      {/* Quick Links */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Quick Links</h2>
        <div className="grid md:grid-cols-3 gap-4">
          <a
            href="/api/health"
            className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-blue-500 transition-colors"
          >
            <h3 className="font-semibold mb-1">Health Check</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">Test backend health endpoint</p>
          </a>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-blue-500 transition-colors"
          >
            <h3 className="font-semibold mb-1">API Docs</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">Interactive OpenAPI documentation</p>
          </a>
          <a
            href="/"
            className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-blue-500 transition-colors"
          >
            <h3 className="font-semibold mb-1">Dashboard</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">Return to main dashboard</p>
          </a>
        </div>
      </section>
    </div>
  );
}
