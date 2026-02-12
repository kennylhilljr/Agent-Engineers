'use client';

import { useEffect, useRef, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Task } from '@/db/schema';
import { ZoomIn, ZoomOut, Maximize } from 'lucide-react';

interface GraphLayoutProps {
  tasks: Task[];
  currentTaskId?: number;
  dependencies?: Array<{ from: number; to: number }>;
}

interface Node {
  id: number;
  x: number;
  y: number;
  task: Task;
}

interface Edge {
  from: number;
  to: number;
}

const statusColors = {
  todo: '#6B7280',
  in_progress: '#3B82F6',
  done: '#10B981',
  blocked: '#EF4444',
};

/**
 * Simple force-directed graph layout using Dagre-like algorithm
 */
function calculateLayout(tasks: Task[], edges: Edge[]): Node[] {
  const nodes: Node[] = [];
  const nodeMap = new Map<number, Node>();

  // Initialize nodes in a grid
  const cols = Math.ceil(Math.sqrt(tasks.length));
  const nodeSpacing = 200;

  tasks.forEach((task, index) => {
    const row = Math.floor(index / cols);
    const col = index % cols;

    const node: Node = {
      id: task.id,
      x: col * nodeSpacing + 100,
      y: row * nodeSpacing + 100,
      task,
    };

    nodes.push(node);
    nodeMap.set(task.id, node);
  });

  // Apply force-directed layout iterations
  const iterations = 50;
  const repulsionStrength = 50000;
  const attractionStrength = 0.01;

  for (let iter = 0; iter < iterations; iter++) {
    const forces = new Map<number, { fx: number; fy: number }>();

    // Initialize forces
    nodes.forEach(node => {
      forces.set(node.id, { fx: 0, fy: 0 });
    });

    // Repulsion between all nodes
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const n1 = nodes[i];
        const n2 = nodes[j];

        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const distSq = dx * dx + dy * dy;
        const dist = Math.sqrt(distSq);

        if (dist > 0) {
          const force = repulsionStrength / distSq;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          const f1 = forces.get(n1.id)!;
          const f2 = forces.get(n2.id)!;

          f1.fx -= fx;
          f1.fy -= fy;
          f2.fx += fx;
          f2.fy += fy;
        }
      }
    }

    // Attraction along edges
    edges.forEach(edge => {
      const from = nodeMap.get(edge.from);
      const to = nodeMap.get(edge.to);

      if (from && to) {
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist > 0) {
          const force = dist * attractionStrength;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          const f1 = forces.get(from.id)!;
          const f2 = forces.get(to.id)!;

          f1.fx += fx;
          f1.fy += fy;
          f2.fx -= fx;
          f2.fy -= fy;
        }
      }
    });

    // Apply forces
    nodes.forEach(node => {
      const f = forces.get(node.id)!;
      node.x += f.fx * 0.1;
      node.y += f.fy * 0.1;
    });
  }

  return nodes;
}

export function GraphLayout({ tasks, currentTaskId, dependencies = [] }: GraphLayoutProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  // Generate layout
  const nodes = calculateLayout(tasks, dependencies);

  // Draw graph
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Apply transformations
    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);

    // Draw edges
    ctx.strokeStyle = '#4B5563';
    ctx.lineWidth = 2;

    dependencies.forEach(edge => {
      const from = nodes.find(n => n.id === edge.from);
      const to = nodes.find(n => n.id === edge.to);

      if (from && to) {
        // Draw arrow
        ctx.beginPath();
        ctx.moveTo(from.x + 75, from.y + 40);
        ctx.lineTo(to.x + 75, to.y + 40);
        ctx.stroke();

        // Arrow head
        const angle = Math.atan2(to.y - from.y, to.x - from.x);
        const arrowSize = 10;
        ctx.beginPath();
        ctx.moveTo(to.x + 75, to.y + 40);
        ctx.lineTo(
          to.x + 75 - arrowSize * Math.cos(angle - Math.PI / 6),
          to.y + 40 - arrowSize * Math.sin(angle - Math.PI / 6)
        );
        ctx.moveTo(to.x + 75, to.y + 40);
        ctx.lineTo(
          to.x + 75 - arrowSize * Math.cos(angle + Math.PI / 6),
          to.y + 40 - arrowSize * Math.sin(angle + Math.PI / 6)
        );
        ctx.stroke();
      }
    });

    // Draw nodes
    nodes.forEach(node => {
      const isCurrent = node.id === currentTaskId;
      const isSelected = selectedNode?.id === node.id;
      const status = node.task.status as keyof typeof statusColors;
      const color = statusColors[status] || '#6B7280';

      // Node background
      ctx.fillStyle = '#1F2937';
      ctx.strokeStyle = isCurrent || isSelected ? '#3B82F6' : color;
      ctx.lineWidth = isCurrent || isSelected ? 4 : 2;

      ctx.beginPath();
      ctx.roundRect(node.x, node.y, 150, 80, 8);
      ctx.fill();
      ctx.stroke();

      // Status indicator
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x + 15, node.y + 15, 6, 0, Math.PI * 2);
      ctx.fill();

      // Text
      ctx.fillStyle = '#FFFFFF';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';

      // Task category
      ctx.fillStyle = '#9CA3AF';
      ctx.fillText(node.task.category.substring(0, 15), node.x + 10, node.y + 30);

      // Task description (truncated)
      ctx.fillStyle = '#FFFFFF';
      const desc = node.task.description.substring(0, 20) + '...';
      ctx.fillText(desc, node.x + 10, node.y + 50);
    });

    ctx.restore();
  }, [nodes, dependencies, zoom, pan, currentTaskId, selectedNode]);

  // Handle mouse events
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleZoomIn = () => {
    setZoom(Math.min(zoom * 1.2, 3));
  };

  const handleZoomOut = () => {
    setZoom(Math.max(zoom / 1.2, 0.3));
  };

  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div className="h-full w-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold mb-2">Dependency Graph</h2>
            <p className="text-gray-400">
              Visualizing task relationships and dependencies
            </p>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleZoomIn}
              className="p-2 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-5 h-5" />
            </button>
            <button
              onClick={handleZoomOut}
              className="p-2 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-5 h-5" />
            </button>
            <button
              onClick={handleReset}
              className="p-2 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors"
              title="Reset View"
            >
              <Maximize className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Canvas */}
      <div
        ref={containerRef}
        className="flex-1 relative bg-gray-950 cursor-move"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <canvas ref={canvasRef} />

        {/* Legend */}
        <div className="absolute bottom-4 left-4 bg-gray-900/90 p-4 rounded-lg border border-gray-700">
          <p className="text-xs text-gray-400 mb-2">Status</p>
          <div className="space-y-2">
            {Object.entries(statusColors).map(([status, color]) => (
              <div key={status} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <span className="text-xs text-gray-300 capitalize">
                  {status.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Instructions */}
        <div className="absolute top-4 right-4 bg-gray-900/90 p-3 rounded-lg border border-gray-700">
          <p className="text-xs text-gray-400">
            Drag to pan • Use zoom controls • Arrows show dependencies
          </p>
        </div>
      </div>
    </div>
  );
}
