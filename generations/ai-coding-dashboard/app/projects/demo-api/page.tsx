'use client';

import React, { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface ApiResponse {
  success: boolean;
  data?: any;
  error?: string;
  message?: string;
}

export default function ApiDemoPage() {
  const [response, setResponse] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [projectId, setProjectId] = useState('');
  const [taskId, setTaskId] = useState('');

  const makeRequest = async (
    endpoint: string,
    method: string = 'GET',
    body?: any
  ) => {
    setLoading(true);
    setResponse(null);

    try {
      const options: RequestInit = {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
      };

      if (body) {
        options.body = JSON.stringify(body);
      }

      const res = await fetch(endpoint, options);
      const data = await res.json();
      setResponse(data);

      // Auto-populate IDs for convenience
      if (data.success && data.data) {
        if (data.data.id && !projectId) {
          setProjectId(data.data.id.toString());
        }
        if (method === 'POST' && endpoint.includes('/tasks') && !endpoint.includes('complete')) {
          setTaskId(data.data.id?.toString() || '');
        }
      }
    } catch (error) {
      setResponse({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-8 max-w-6xl">
      <h1 className="text-4xl font-bold mb-8">Task Execution API Demo</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div>
          <label className="block text-sm font-medium mb-2">Project ID</label>
          <input
            type="text"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            placeholder="Enter project ID"
            className="w-full px-3 py-2 border rounded"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">Task ID</label>
          <input
            type="text"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            placeholder="Enter task ID"
            className="w-full px-3 py-2 border rounded"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Projects Section */}
        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4">Projects</h2>
          <div className="space-y-2">
            <Button
              onClick={() => makeRequest('/api/projects')}
              disabled={loading}
              className="w-full"
            >
              GET /api/projects
            </Button>
            <Button
              onClick={() =>
                makeRequest('/api/projects', 'POST', {
                  name: 'Demo Project ' + Date.now(),
                  spec: 'This is a demo project created from the API demo page',
                  userId: 'demo-user-' + Date.now(),
                  preferredLayout: 'kanban',
                  specData: {
                    tasks: [
                      {
                        category: 'setup',
                        description: 'Initialize project',
                        steps: ['Create repo', 'Set up dev environment'],
                      },
                    ],
                  },
                })
              }
              disabled={loading}
              className="w-full"
            >
              POST /api/projects
            </Button>
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}`)}
              disabled={loading || !projectId}
              className="w-full"
            >
              GET /api/projects/[id]
            </Button>
            <Button
              onClick={() =>
                makeRequest(`/api/projects/${projectId}`, 'PATCH', {
                  name: 'Updated Project Name',
                  preferredLayout: 'table',
                })
              }
              disabled={loading || !projectId}
              className="w-full"
            >
              PATCH /api/projects/[id]
            </Button>
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}`, 'DELETE')}
              disabled={loading || !projectId}
              className="w-full"
              variant="destructive"
            >
              DELETE /api/projects/[id]
            </Button>
          </div>
        </Card>

        {/* Tasks Section */}
        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4">Tasks</h2>
          <div className="space-y-2">
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}/tasks`)}
              disabled={loading || !projectId}
              className="w-full"
            >
              GET /tasks
            </Button>
            <Button
              onClick={() =>
                makeRequest(`/api/projects/${projectId}/tasks`, 'POST', {
                  category: 'frontend',
                  description: 'Build dashboard UI',
                  steps: ['Design mockups', 'Implement components', 'Add styling'],
                  status: 'todo',
                })
              }
              disabled={loading || !projectId}
              className="w-full"
            >
              POST /tasks
            </Button>
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}/tasks/${taskId}`)}
              disabled={loading || !projectId || !taskId}
              className="w-full"
            >
              GET /tasks/[taskId]
            </Button>
            <Button
              onClick={() =>
                makeRequest(`/api/projects/${projectId}/tasks/${taskId}`, 'PATCH', {
                  status: 'in_progress',
                  agentNotes: 'Started working on this task',
                })
              }
              disabled={loading || !projectId || !taskId}
              className="w-full"
            >
              PATCH /tasks/[taskId]
            </Button>
            <Button
              onClick={() =>
                makeRequest(`/api/projects/${projectId}/tasks/${taskId}/complete`, 'POST', {
                  success: true,
                  notes: 'Completed successfully',
                  filesChanged: ['file1.tsx', 'file2.ts'],
                })
              }
              disabled={loading || !projectId || !taskId}
              className="w-full"
            >
              POST /tasks/[taskId]/complete
            </Button>
          </div>
        </Card>

        {/* Execution Control Section */}
        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4">Execution</h2>
          <div className="space-y-2">
            <Button
              onClick={() =>
                makeRequest(`/api/projects/${projectId}/start`, 'POST', {
                  autoApprove: false,
                })
              }
              disabled={loading || !projectId}
              className="w-full"
            >
              POST /start
            </Button>
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}/pause`, 'POST', {})}
              disabled={loading || !projectId}
              className="w-full"
            >
              POST /pause
            </Button>
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}/resume`, 'POST', {})}
              disabled={loading || !projectId}
              className="w-full"
            >
              POST /resume
            </Button>
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}/stop`, 'POST', {})}
              disabled={loading || !projectId}
              className="w-full"
            >
              POST /stop
            </Button>
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}/status`)}
              disabled={loading || !projectId}
              className="w-full"
            >
              GET /status
            </Button>
          </div>
        </Card>

        {/* Events Section */}
        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4">Events</h2>
          <div className="space-y-2">
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}/events`)}
              disabled={loading || !projectId}
              className="w-full"
            >
              GET /events
            </Button>
            <Button
              onClick={() =>
                makeRequest(`/api/projects/${projectId}/events?eventType=activity&limit=10`)
              }
              disabled={loading || !projectId}
              className="w-full"
            >
              GET /events (filtered)
            </Button>
            <Button
              onClick={() =>
                makeRequest(`/api/projects/${projectId}/events`, 'POST', {
                  eventType: 'milestone',
                  eventData: {
                    milestone_name: 'MVP Complete',
                    description: 'Completed minimum viable product',
                    completion_percentage: 50,
                  },
                  agentReasoning: 'Reached important milestone',
                })
              }
              disabled={loading || !projectId}
              className="w-full"
            >
              POST /events
            </Button>
          </div>
        </Card>

        {/* Responses Section */}
        <Card className="p-6">
          <h2 className="text-2xl font-semibold mb-4">Responses</h2>
          <div className="space-y-2">
            <Button
              onClick={() => makeRequest(`/api/projects/${projectId}/pending-responses`)}
              disabled={loading || !projectId}
              className="w-full"
            >
              GET /pending-responses
            </Button>
            <Button
              onClick={() =>
                makeRequest(`/api/projects/${projectId}/events`, 'POST', {
                  eventType: 'decision_needed',
                  eventData: {
                    decision_id: 'demo-decision-' + Date.now(),
                    question: 'Which database to use?',
                    options: ['PostgreSQL', 'MySQL', 'MongoDB'],
                    priority: 'high',
                  },
                })
              }
              disabled={loading || !projectId}
              className="w-full"
            >
              Create Decision (Test)
            </Button>
            <Button
              onClick={() =>
                makeRequest(`/api/projects/${projectId}/responses`, 'POST', {
                  responseType: 'decision',
                  responseId: 'demo-decision-123',
                  value: 'PostgreSQL',
                  notes: 'Best choice for our needs',
                })
              }
              disabled={loading || !projectId}
              className="w-full"
            >
              POST /responses (decision)
            </Button>
          </div>
        </Card>
      </div>

      {/* Response Display */}
      {response && (
        <Card className="mt-8 p-6">
          <h2 className="text-2xl font-semibold mb-4">Response</h2>
          <div
            className={`p-4 rounded ${
              response.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
            }`}
          >
            <pre className="text-sm overflow-auto max-h-96">
              {JSON.stringify(response, null, 2)}
            </pre>
          </div>
        </Card>
      )}

      {loading && (
        <div className="mt-8 text-center">
          <p className="text-lg">Loading...</p>
        </div>
      )}
    </div>
  );
}
