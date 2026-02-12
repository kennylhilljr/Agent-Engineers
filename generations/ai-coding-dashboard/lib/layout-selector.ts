/**
 * Layout Selection Engine
 *
 * Analyzes project specifications and determines the optimal layout
 * for task visualization: kanban, timeline, or graph.
 */

import { Task } from '@/db/schema';

export type LayoutType = 'kanban' | 'timeline' | 'graph';

export interface AppSpec {
  tasks?: Array<{
    category: string;
    description: string;
    steps?: string[];
    dependsOn?: string[]; // Task dependencies
    estimatedHours?: number;
    priority?: number;
  }>;
  name?: string;
  dependencies?: Record<string, string[]>; // Global dependency map
}

export interface LayoutAnalysis {
  layout: LayoutType;
  confidence: number; // 0-1
  reasoning: string;
  metrics: {
    taskCount: number;
    dependencyCount: number;
    maxDependencyDepth: number;
    hasBranching: boolean;
    isLinear: boolean;
    hasTimelines: boolean;
  };
}

/**
 * Detect optimal layout for a project specification
 */
export function detectOptimalLayout(spec: AppSpec): LayoutAnalysis {
  const tasks = spec.tasks || [];
  const taskCount = tasks.length;

  // Build dependency graph
  const dependencyGraph = buildDependencyGraph(spec);
  const dependencyCount = dependencyGraph.edges.length;

  // Analyze graph structure
  const maxDepth = calculateMaxDepth(dependencyGraph);
  const hasBranching = detectBranching(dependencyGraph);
  const isLinear = dependencyCount > 0 && !hasBranching;
  const hasTimelines = tasks.some(t => t.estimatedHours !== undefined);

  const metrics = {
    taskCount,
    dependencyCount,
    maxDependencyDepth: maxDepth,
    hasBranching,
    isLinear,
    hasTimelines,
  };

  // Decision logic

  // 1. Complex dependencies → Graph
  if (dependencyCount > 5 && hasBranching) {
    return {
      layout: 'graph',
      confidence: 0.9,
      reasoning: `Project has ${dependencyCount} dependencies with complex branching. Graph view best shows the dependency structure.`,
      metrics,
    };
  }

  // 2. Sequential/Linear dependencies → Timeline
  if (isLinear && dependencyCount > 0) {
    return {
      layout: 'timeline',
      confidence: 0.85,
      reasoning: `Project has linear task dependencies. Timeline view best shows the sequential workflow.`,
      metrics,
    };
  }

  // 3. Time-based project → Timeline
  if (hasTimelines && taskCount > 10) {
    return {
      layout: 'timeline',
      confidence: 0.8,
      reasoning: `Project includes time estimates. Timeline view best shows scheduling.`,
      metrics,
    };
  }

  // 4. Simple dependencies → Graph (light)
  if (dependencyCount > 0 && dependencyCount <= 5) {
    return {
      layout: 'graph',
      confidence: 0.7,
      reasoning: `Project has ${dependencyCount} dependencies. Graph view shows task relationships clearly.`,
      metrics,
    };
  }

  // 5. Large project without dependencies → Kanban
  if (taskCount > 20 && dependencyCount === 0) {
    return {
      layout: 'kanban',
      confidence: 0.75,
      reasoning: `Project has ${taskCount} tasks without dependencies. Kanban view best for status management.`,
      metrics,
    };
  }

  // 6. Default: Small project → Kanban
  return {
    layout: 'kanban',
    confidence: 0.8,
    reasoning: `Project has ${taskCount} tasks. Kanban view provides simple, effective task management.`,
    metrics,
  };
}

/**
 * Build dependency graph from spec
 */
interface DependencyGraph {
  nodes: Set<string>;
  edges: Array<{ from: string; to: string }>;
  adjacencyList: Map<string, string[]>;
}

function buildDependencyGraph(spec: AppSpec): DependencyGraph {
  const nodes = new Set<string>();
  const edges: Array<{ from: string; to: string }> = [];
  const adjacencyList = new Map<string, string[]>();

  const tasks = spec.tasks || [];

  // Add all tasks as nodes
  tasks.forEach((task, index) => {
    const taskId = task.description.substring(0, 20) || `task-${index}`;
    nodes.add(taskId);
    adjacencyList.set(taskId, []);
  });

  // Add edges from task dependencies
  tasks.forEach((task, index) => {
    const taskId = task.description.substring(0, 20) || `task-${index}`;
    const deps = task.dependsOn || [];

    deps.forEach(dep => {
      edges.push({ from: dep, to: taskId });
      const list = adjacencyList.get(dep) || [];
      list.push(taskId);
      adjacencyList.set(dep, list);
    });
  });

  // Add edges from global dependency map
  if (spec.dependencies) {
    Object.entries(spec.dependencies).forEach(([from, toList]) => {
      toList.forEach(to => {
        edges.push({ from, to });
        const list = adjacencyList.get(from) || [];
        list.push(to);
        adjacencyList.set(from, list);
      });
    });
  }

  return { nodes, edges, adjacencyList };
}

/**
 * Calculate maximum dependency depth (longest path)
 */
function calculateMaxDepth(graph: DependencyGraph): number {
  const { adjacencyList } = graph;
  const visited = new Set<string>();
  let maxDepth = 0;

  function dfs(node: string, depth: number): number {
    if (visited.has(node)) return depth;
    visited.add(node);

    const neighbors = adjacencyList.get(node) || [];
    if (neighbors.length === 0) return depth;

    let maxChildDepth = depth;
    neighbors.forEach(neighbor => {
      const childDepth = dfs(neighbor, depth + 1);
      maxChildDepth = Math.max(maxChildDepth, childDepth);
    });

    return maxChildDepth;
  }

  // Find root nodes (nodes with no incoming edges)
  const allNodes = Array.from(graph.nodes);
  const hasIncoming = new Set<string>();
  graph.edges.forEach(edge => hasIncoming.add(edge.to));

  const rootNodes = allNodes.filter(node => !hasIncoming.has(node));

  // Calculate depth from each root
  rootNodes.forEach(root => {
    const depth = dfs(root, 0);
    maxDepth = Math.max(maxDepth, depth);
  });

  return maxDepth;
}

/**
 * Detect if graph has branching (one node has multiple children)
 */
function detectBranching(graph: DependencyGraph): boolean {
  const { adjacencyList } = graph;

  for (const [, neighbors] of adjacencyList) {
    if (neighbors.length > 1) return true;
  }

  return false;
}

/**
 * Detect optimal layout from existing tasks (database)
 */
export function detectLayoutFromTasks(tasks: Task[]): LayoutAnalysis {
  // Convert Task[] to AppSpec format
  const spec: AppSpec = {
    tasks: tasks.map(task => ({
      category: task.category,
      description: task.description,
      steps: Array.isArray(task.steps) ? task.steps : [],
      // TODO: Add dependency support to Task schema
      dependsOn: [],
      estimatedHours: undefined,
      priority: 1,
    })),
  };

  return detectOptimalLayout(spec);
}
