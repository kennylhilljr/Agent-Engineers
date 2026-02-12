'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { KanbanLayout } from '@/components/layouts/kanban-layout';
import { TimelineLayout } from '@/components/layouts/timeline-layout';
import { GraphLayout } from '@/components/layouts/graph-layout';
import { Task } from '@/db/schema';
import { detectLayoutFromTasks, LayoutType } from '@/lib/layout-selector';
import { Badge } from '@/components/ui/badge';
import { LayoutGrid, Clock, Network } from 'lucide-react';

export default function ProjectPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [tasks, setTasks] = useState<Task[]>([]);
  const [currentLayout, setCurrentLayout] = useState<LayoutType>('kanban');
  const [detectedLayout, setDetectedLayout] = useState<LayoutType>('kanban');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch tasks from API
  useEffect(() => {
    async function fetchTasks() {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/projects/${projectId}/tasks`);
        if (!response.ok) {
          throw new Error('Failed to fetch tasks');
        }

        const result = await response.json();
        if (result.success) {
          setTasks(result.data);

          // Detect optimal layout
          const analysis = detectLayoutFromTasks(result.data);
          setDetectedLayout(analysis.layout);
          setCurrentLayout(analysis.layout);
        } else {
          throw new Error(result.error || 'Failed to load tasks');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        console.error('Error fetching tasks:', err);
      } finally {
        setIsLoading(false);
      }
    }

    fetchTasks();
  }, [projectId]);

  // Handle task update
  const handleTaskUpdate = async (task: Task, newStatus: string) => {
    try {
      const response = await fetch(`/api/projects/${projectId}/tasks/${task.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) {
        throw new Error('Failed to update task');
      }

      // Refresh tasks
      const updatedTasks = tasks.map(t =>
        t.id === task.id ? { ...t, status: newStatus } : t
      );
      setTasks(updatedTasks);
    } catch (err) {
      console.error('Error updating task:', err);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-white mx-auto mb-4"></div>
          <p className="text-gray-400">Loading project...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 mb-4">Error</div>
          <p className="text-gray-400">{error}</p>
        </div>
      </div>
    );
  }

  const layoutIcons = {
    kanban: LayoutGrid,
    timeline: Clock,
    graph: Network,
  };

  const layoutLabels = {
    kanban: 'Kanban Board',
    timeline: 'Timeline View',
    graph: 'Dependency Graph',
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Layout Switcher */}
      <div className="border-b border-gray-800 bg-gray-950">
        <div className="max-w-7xl mx-auto px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold mb-1">Project Dashboard</h1>
              <p className="text-sm text-gray-400">
                Layout auto-selected based on project structure
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">View:</span>
              {(['kanban', 'timeline', 'graph'] as LayoutType[]).map(layout => {
                const Icon = layoutIcons[layout];
                const isActive = currentLayout === layout;
                const isRecommended = detectedLayout === layout;

                return (
                  <button
                    key={layout}
                    onClick={() => setCurrentLayout(layout)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-sm">{layoutLabels[layout]}</span>
                    {isRecommended && !isActive && (
                      <Badge variant="outline" className="text-xs ml-1">
                        Recommended
                      </Badge>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Layout Content */}
      <div className="h-[calc(100vh-120px)]">
        {currentLayout === 'kanban' && (
          <KanbanLayout
            tasks={tasks}
            onTaskUpdate={handleTaskUpdate}
          />
        )}

        {currentLayout === 'timeline' && (
          <TimelineLayout tasks={tasks} />
        )}

        {currentLayout === 'graph' && (
          <GraphLayout tasks={tasks} dependencies={[]} />
        )}
      </div>
    </div>
  );
}
