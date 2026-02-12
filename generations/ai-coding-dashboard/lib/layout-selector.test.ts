/**
 * Unit Tests for Layout Selector
 */

import { describe, it, expect } from 'vitest';
import { detectOptimalLayout, AppSpec, LayoutType } from './layout-selector';

describe('Layout Selector', () => {
  describe('detectOptimalLayout', () => {
    it('should select kanban for small projects without dependencies', () => {
      const spec: AppSpec = {
        name: 'Simple Project',
        tasks: [
          { category: 'frontend', description: 'Build homepage' },
          { category: 'backend', description: 'Create API' },
          { category: 'testing', description: 'Write tests' },
        ],
      };

      const result = detectOptimalLayout(spec);

      expect(result.layout).toBe('kanban');
      expect(result.metrics.taskCount).toBe(3);
      expect(result.metrics.dependencyCount).toBe(0);
      expect(result.confidence).toBeGreaterThan(0.7);
    });

    it('should select timeline for sequential dependencies', () => {
      const spec: AppSpec = {
        name: 'Sequential Project',
        tasks: [
          { category: 'setup', description: 'Initialize project', dependsOn: [] },
          { category: 'frontend', description: 'Build UI', dependsOn: ['Initialize project'] },
          { category: 'backend', description: 'Create API', dependsOn: ['Build UI'] },
          { category: 'deploy', description: 'Deploy app', dependsOn: ['Create API'] },
        ],
      };

      const result = detectOptimalLayout(spec);

      expect(result.layout).toBe('timeline');
      expect(result.metrics.dependencyCount).toBeGreaterThan(0);
      expect(result.metrics.isLinear).toBe(true);
      expect(result.metrics.hasBranching).toBe(false);
      expect(result.confidence).toBeGreaterThan(0.8);
    });

    it('should select graph for complex branching dependencies', () => {
      const spec: AppSpec = {
        name: 'Complex Project',
        tasks: [
          { category: 'setup', description: 'Task A', dependsOn: [] },
          { category: 'feature1', description: 'Task B', dependsOn: ['Task A'] },
          { category: 'feature2', description: 'Task C', dependsOn: ['Task A'] },
          { category: 'feature3', description: 'Task D', dependsOn: ['Task A'] },
          { category: 'integration', description: 'Task E', dependsOn: ['Task B', 'Task C'] },
          { category: 'testing', description: 'Task F', dependsOn: ['Task D', 'Task E'] },
        ],
      };

      const result = detectOptimalLayout(spec);

      expect(result.layout).toBe('graph');
      expect(result.metrics.hasBranching).toBe(true);
      expect(result.metrics.dependencyCount).toBeGreaterThan(5);
      expect(result.confidence).toBeGreaterThan(0.8);
    });

    it('should select timeline for time-based projects', () => {
      const spec: AppSpec = {
        name: 'Time-Based Project',
        tasks: [
          { category: 'phase1', description: 'Sprint 1', estimatedHours: 40 },
          { category: 'phase2', description: 'Sprint 2', estimatedHours: 40 },
          { category: 'phase3', description: 'Sprint 3', estimatedHours: 40 },
          { category: 'phase4', description: 'Sprint 4', estimatedHours: 40 },
          { category: 'phase5', description: 'Sprint 5', estimatedHours: 40 },
          { category: 'phase6', description: 'Sprint 6', estimatedHours: 40 },
          { category: 'phase7', description: 'Sprint 7', estimatedHours: 40 },
          { category: 'phase8', description: 'Sprint 8', estimatedHours: 40 },
          { category: 'phase9', description: 'Sprint 9', estimatedHours: 40 },
          { category: 'phase10', description: 'Sprint 10', estimatedHours: 40 },
          { category: 'phase11', description: 'Sprint 11', estimatedHours: 40 },
        ],
      };

      const result = detectOptimalLayout(spec);

      expect(result.layout).toBe('timeline');
      expect(result.metrics.hasTimelines).toBe(true);
      expect(result.metrics.taskCount).toBeGreaterThan(10);
    });

    it('should select kanban for large projects without dependencies', () => {
      const spec: AppSpec = {
        name: 'Large Project',
        tasks: Array.from({ length: 25 }, (_, i) => ({
          category: 'feature',
          description: `Feature ${i + 1}`,
        })),
      };

      const result = detectOptimalLayout(spec);

      expect(result.layout).toBe('kanban');
      expect(result.metrics.taskCount).toBe(25);
      expect(result.metrics.dependencyCount).toBe(0);
    });

    it('should select graph for light dependencies', () => {
      const spec: AppSpec = {
        name: 'Light Dependencies',
        tasks: [
          { category: 'setup', description: 'Task A' },
          { category: 'feature', description: 'Task B', dependsOn: ['Task A'] },
          { category: 'feature', description: 'Task C', dependsOn: ['Task A'] },
          { category: 'deploy', description: 'Task D' },
        ],
      };

      const result = detectOptimalLayout(spec);

      expect(result.layout).toBe('graph');
      expect(result.metrics.dependencyCount).toBeGreaterThan(0);
      expect(result.metrics.dependencyCount).toBeLessThanOrEqual(5);
    });

    it('should handle empty task list', () => {
      const spec: AppSpec = {
        name: 'Empty Project',
        tasks: [],
      };

      const result = detectOptimalLayout(spec);

      expect(result.layout).toBe('kanban');
      expect(result.metrics.taskCount).toBe(0);
    });

    it('should handle global dependency map', () => {
      const spec: AppSpec = {
        name: 'Global Deps',
        tasks: [
          { category: 'a', description: 'Task A' },
          { category: 'b', description: 'Task B' },
          { category: 'c', description: 'Task C' },
          { category: 'd', description: 'Task D' },
        ],
        dependencies: {
          'Task A': ['Task B', 'Task C'],
          'Task B': ['Task D'],
          'Task C': ['Task D'],
        },
      };

      const result = detectOptimalLayout(spec);

      expect(result.layout).toBe('graph');
      expect(result.metrics.dependencyCount).toBeGreaterThan(0);
    });

    it('should calculate max dependency depth correctly', () => {
      const spec: AppSpec = {
        name: 'Deep Dependencies',
        tasks: [
          { category: 'a', description: 'Task A' },
          { category: 'b', description: 'Task B', dependsOn: ['Task A'] },
          { category: 'c', description: 'Task C', dependsOn: ['Task B'] },
          { category: 'd', description: 'Task D', dependsOn: ['Task C'] },
          { category: 'e', description: 'Task E', dependsOn: ['Task D'] },
        ],
      };

      const result = detectOptimalLayout(spec);

      expect(result.metrics.maxDependencyDepth).toBeGreaterThan(0);
      expect(result.layout).toBe('timeline'); // Linear chain
    });

    it('should provide meaningful reasoning', () => {
      const spec: AppSpec = {
        name: 'Test Project',
        tasks: [
          { category: 'test', description: 'Task 1' },
          { category: 'test', description: 'Task 2' },
        ],
      };

      const result = detectOptimalLayout(spec);

      expect(result.reasoning).toBeTruthy();
      expect(result.reasoning.length).toBeGreaterThan(0);
      expect(result.reasoning).toContain('task');
    });

    it('should have confidence between 0 and 1', () => {
      const specs: AppSpec[] = [
        { tasks: [] },
        { tasks: [{ category: 'test', description: 'Test' }] },
        {
          tasks: [
            { category: 'a', description: 'A', dependsOn: [] },
            { category: 'b', description: 'B', dependsOn: ['A'] },
          ],
        },
      ];

      specs.forEach(spec => {
        const result = detectOptimalLayout(spec);
        expect(result.confidence).toBeGreaterThanOrEqual(0);
        expect(result.confidence).toBeLessThanOrEqual(1);
      });
    });

    it('should detect branching correctly', () => {
      const linearSpec: AppSpec = {
        tasks: [
          { category: 'a', description: 'A' },
          { category: 'b', description: 'B', dependsOn: ['A'] },
          { category: 'c', description: 'C', dependsOn: ['B'] },
        ],
      };

      const branchingSpec: AppSpec = {
        tasks: [
          { category: 'a', description: 'A' },
          { category: 'b', description: 'B', dependsOn: ['A'] },
          { category: 'c', description: 'C', dependsOn: ['A'] },
        ],
      };

      const linearResult = detectOptimalLayout(linearSpec);
      const branchingResult = detectOptimalLayout(branchingSpec);

      expect(linearResult.metrics.hasBranching).toBe(false);
      expect(branchingResult.metrics.hasBranching).toBe(true);
    });
  });
});
