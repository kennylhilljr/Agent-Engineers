'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

/**
 * Agent Tools Demo Page
 *
 * Interactive demo page to test all agent tools:
 * - File operations (read, write, list)
 * - Task management (create, update, complete)
 * - Project state queries
 * - Event logging
 */

interface ToolResult {
  success: boolean;
  data?: any;
  error?: string;
  timestamp?: string;
}

export default function AgentToolsDemo() {
  const [results, setResults] = useState<{ [key: string]: ToolResult }>({});
  const [loading, setLoading] = useState<{ [key: string]: boolean }>({});

  // Helper to call tool API
  const callTool = async (toolName: string, params: any = {}) => {
    setLoading((prev) => ({ ...prev, [toolName]: true }));

    try {
      const response = await fetch('/api/agent/tools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: toolName, params }),
      });

      const result = await response.json();
      setResults((prev) => ({ ...prev, [toolName]: result }));
    } catch (error) {
      setResults((prev) => ({
        ...prev,
        [toolName]: {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        },
      }));
    } finally {
      setLoading((prev) => ({ ...prev, [toolName]: false }));
    }
  };

  // Render result panel
  const ResultPanel = ({ toolName }: { toolName: string }) => {
    const result = results[toolName];
    if (!result) return null;

    return (
      <div
        className={`mt-2 p-4 rounded-lg border ${
          result.success
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}
      >
        <div className="flex items-center gap-2 mb-2">
          <span
            className={`font-semibold ${
              result.success ? 'text-green-700' : 'text-red-700'
            }`}
          >
            {result.success ? '✓ Success' : '✗ Error'}
          </span>
          {result.timestamp && (
            <span className="text-xs text-gray-500">{result.timestamp}</span>
          )}
        </div>

        {result.error && (
          <div className="text-red-700 text-sm mb-2">{result.error}</div>
        )}

        {result.data && (
          <pre className="text-xs bg-white p-2 rounded overflow-auto max-h-64">
            {JSON.stringify(result.data, null, 2)}
          </pre>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Agent Tools Demo
          </h1>
          <p className="text-gray-600 mb-6">
            Interactive testing interface for Pydantic AI agent tools
          </p>

          {/* File Operations Section */}
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">
              File Operations
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Read File */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">Read File</h3>
                <p className="text-sm text-gray-600 mb-3">
                  Read contents of README.md
                </p>
                <Button
                  onClick={() =>
                    callTool('read_file', { path: 'README.md' })
                  }
                  disabled={loading.read_file}
                  className="w-full"
                >
                  {loading.read_file ? 'Reading...' : 'Read README.md'}
                </Button>
                <ResultPanel toolName="read_file" />
              </div>

              {/* Write File */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">Write File</h3>
                <p className="text-sm text-gray-600 mb-3">
                  Create a test file
                </p>
                <Button
                  onClick={() =>
                    callTool('write_file', {
                      path: 'test_output.txt',
                      content: `Test file created at ${new Date().toISOString()}\nHello from Agent Tools!`,
                    })
                  }
                  disabled={loading.write_file}
                  className="w-full"
                >
                  {loading.write_file ? 'Writing...' : 'Write Test File'}
                </Button>
                <ResultPanel toolName="write_file" />
              </div>

              {/* List Files */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">List Files</h3>
                <p className="text-sm text-gray-600 mb-3">
                  List files in project root
                </p>
                <Button
                  onClick={() =>
                    callTool('list_files', { directory: '.', recursive: false })
                  }
                  disabled={loading.list_files}
                  className="w-full"
                >
                  {loading.list_files ? 'Listing...' : 'List Files'}
                </Button>
                <ResultPanel toolName="list_files" />
              </div>
            </div>
          </section>

          <Separator className="my-8" />

          {/* Task Management Section */}
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">
              Task Management
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Create Task */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">
                  Create Task
                </h3>
                <p className="text-sm text-gray-600 mb-3">
                  Create a new feature task
                </p>
                <Button
                  onClick={() =>
                    callTool('create_task', {
                      project_id: 'DEMO-001',
                      title: `TASK-${Date.now()}`,
                      description: 'Demo task created from UI',
                      category: 'feature',
                    })
                  }
                  disabled={loading.create_task}
                  className="w-full"
                >
                  {loading.create_task ? 'Creating...' : 'Create Task'}
                </Button>
                <ResultPanel toolName="create_task" />
              </div>

              {/* Update Task */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">
                  Update Task
                </h3>
                <p className="text-sm text-gray-600 mb-3">
                  Update task status to in_progress
                </p>
                <Button
                  onClick={() => {
                    const taskResult = results.create_task;
                    if (taskResult?.success && taskResult.data?.id) {
                      callTool('update_task', {
                        task_id: taskResult.data.id,
                        project_id: 'DEMO-001',
                        status: 'in_progress',
                        notes: 'Started working on this task',
                      });
                    } else {
                      alert('Please create a task first');
                    }
                  }}
                  disabled={loading.update_task}
                  className="w-full"
                >
                  {loading.update_task ? 'Updating...' : 'Update Task'}
                </Button>
                <ResultPanel toolName="update_task" />
              </div>

              {/* Complete Task */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">
                  Complete Task
                </h3>
                <p className="text-sm text-gray-600 mb-3">
                  Mark task as completed
                </p>
                <Button
                  onClick={() => {
                    const taskResult = results.create_task;
                    if (taskResult?.success && taskResult.data?.id) {
                      callTool('complete_task', {
                        task_id: taskResult.data.id,
                        project_id: 'DEMO-001',
                        result_notes: 'Task completed successfully via UI',
                      });
                    } else {
                      alert('Please create a task first');
                    }
                  }}
                  disabled={loading.complete_task}
                  className="w-full"
                >
                  {loading.complete_task ? 'Completing...' : 'Complete Task'}
                </Button>
                <ResultPanel toolName="complete_task" />
              </div>
            </div>
          </section>

          <Separator className="my-8" />

          {/* Project State Section */}
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">
              Project State
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Get Project State */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">
                  Get Project State
                </h3>
                <p className="text-sm text-gray-600 mb-3">
                  Retrieve all tasks and project info
                </p>
                <Button
                  onClick={() =>
                    callTool('get_project_state', { project_id: 'DEMO-001' })
                  }
                  disabled={loading.get_project_state}
                  className="w-full"
                >
                  {loading.get_project_state
                    ? 'Loading...'
                    : 'Get Project State'}
                </Button>
                <ResultPanel toolName="get_project_state" />
              </div>

              {/* Reset State */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">
                  Reset State
                </h3>
                <p className="text-sm text-gray-600 mb-3">
                  Clear all tasks and events (for testing)
                </p>
                <Button
                  onClick={() => callTool('reset_state', {})}
                  disabled={loading.reset_state}
                  variant="destructive"
                  className="w-full"
                >
                  {loading.reset_state ? 'Resetting...' : 'Reset All State'}
                </Button>
                <ResultPanel toolName="reset_state" />
              </div>
            </div>
          </section>

          <Separator className="my-8" />

          {/* Event Logging Section */}
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">
              Event Logging
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Log Event */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">Log Event</h3>
                <p className="text-sm text-gray-600 mb-3">
                  Create a custom event log entry
                </p>
                <Button
                  onClick={() =>
                    callTool('log_event', {
                      project_id: 'DEMO-001',
                      event_type: 'demo_action',
                      details: {
                        action: 'button_click',
                        timestamp: new Date().toISOString(),
                        user: 'demo_user',
                      },
                    })
                  }
                  disabled={loading.log_event}
                  className="w-full"
                >
                  {loading.log_event ? 'Logging...' : 'Log Event'}
                </Button>
                <ResultPanel toolName="log_event" />
              </div>

              {/* Get Events */}
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">Get Events</h3>
                <p className="text-sm text-gray-600 mb-3">
                  Retrieve recent activity log
                </p>
                <Button
                  onClick={() =>
                    callTool('get_events', {
                      project_id: 'DEMO-001',
                      limit: 10,
                    })
                  }
                  disabled={loading.get_events}
                  className="w-full"
                >
                  {loading.get_events ? 'Loading...' : 'Get Events'}
                </Button>
                <ResultPanel toolName="get_events" />
              </div>
            </div>
          </section>

          <Separator className="my-8" />

          {/* Security Tests Section */}
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">
              Security Tests
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Path Traversal Test */}
              <div className="border rounded-lg p-4 bg-yellow-50">
                <h3 className="font-semibold text-gray-700 mb-2">
                  Path Traversal (Should Fail)
                </h3>
                <p className="text-sm text-gray-600 mb-3">
                  Attempt to read /etc/passwd
                </p>
                <Button
                  onClick={() =>
                    callTool('read_file', {
                      path: '../../../etc/passwd',
                    })
                  }
                  disabled={loading.security_traversal}
                  variant="outline"
                  className="w-full"
                >
                  {loading.security_traversal ? 'Testing...' : 'Test Traversal'}
                </Button>
                <ResultPanel toolName="security_traversal" />
              </div>

              {/* Large File Test */}
              <div className="border rounded-lg p-4 bg-yellow-50">
                <h3 className="font-semibold text-gray-700 mb-2">
                  Large File (Should Fail)
                </h3>
                <p className="text-sm text-gray-600 mb-3">
                  Attempt to write 10MB file
                </p>
                <Button
                  onClick={() =>
                    callTool('write_file', {
                      path: 'large_file.txt',
                      content: 'X'.repeat(10 * 1024 * 1024),
                    })
                  }
                  disabled={loading.security_large}
                  variant="outline"
                  className="w-full"
                >
                  {loading.security_large ? 'Testing...' : 'Test Large File'}
                </Button>
                <ResultPanel toolName="security_large" />
              </div>

              {/* Invalid Category Test */}
              <div className="border rounded-lg p-4 bg-yellow-50">
                <h3 className="font-semibold text-gray-700 mb-2">
                  Invalid Category (Should Fail)
                </h3>
                <p className="text-sm text-gray-600 mb-3">
                  Create task with invalid category
                </p>
                <Button
                  onClick={() =>
                    callTool('create_task', {
                      project_id: 'DEMO-001',
                      title: 'INVALID-TASK',
                      description: 'Should fail',
                      category: 'invalid_category',
                    })
                  }
                  disabled={loading.security_category}
                  variant="outline"
                  className="w-full"
                >
                  {loading.security_category
                    ? 'Testing...'
                    : 'Test Invalid Category'}
                </Button>
                <ResultPanel toolName="security_category" />
              </div>
            </div>
          </section>

          {/* Clear Results Button */}
          <div className="flex justify-center mt-8">
            <Button
              onClick={() => setResults({})}
              variant="outline"
              className="px-8"
            >
              Clear All Results
            </Button>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-gray-600">
          <p>
            Agent Tools Demo - Testing file operations, task management, and
            event logging
          </p>
          <p className="mt-2">
            All operations are sandboxed and validated for security
          </p>
        </div>
      </div>
    </div>
  );
}
