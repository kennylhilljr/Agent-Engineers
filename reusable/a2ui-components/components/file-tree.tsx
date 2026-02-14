'use client';

import React, { useState } from 'react';
import { File, Folder, FolderOpen, ChevronRight } from 'lucide-react';

/**
 * FileTree Component - a2ui.FileTree
 * Displays a hierarchical file/folder structure with expand/collapse functionality
 */

export interface FileNode {
  path: string;
  name: string;
  type: 'file' | 'directory';
  modified?: boolean;
  children?: FileNode[];
}

export interface FileTreeData {
  nodes: FileNode[];
  expandedPaths?: string[];
  selectedPath?: string;
}

export interface FileTreeProps {
  type: 'a2ui.FileTree';
  data: FileTreeData;
  onEvent?: (eventType: string, payload: any) => void;
}

export function FileTree({ data, onEvent }: FileTreeProps) {
  const { nodes, expandedPaths: initialExpandedPaths = [], selectedPath: initialSelectedPath } = data;

  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(
    new Set(initialExpandedPaths)
  );
  const [selectedPath, setSelectedPath] = useState<string | undefined>(initialSelectedPath);

  const toggleExpand = (path: string) => {
    const newExpanded = new Set(expandedPaths);
    const isExpanding = !newExpanded.has(path);

    if (isExpanding) {
      newExpanded.add(path);
    } else {
      newExpanded.delete(path);
    }

    setExpandedPaths(newExpanded);

    onEvent?.('expand', {
      path,
      expanded: isExpanding,
    });
  };

  const handleFileClick = (node: FileNode) => {
    setSelectedPath(node.path);
    onEvent?.('click', {
      path: node.path,
    });
  };

  const handleDirectoryClick = (node: FileNode) => {
    toggleExpand(node.path);
  };

  const renderNode = (node: FileNode, depth: number = 0) => {
    const isDirectory = node.type === 'directory';
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expandedPaths.has(node.path);
    const isSelected = selectedPath === node.path;

    return (
      <div key={node.path}>
        <div
          data-testid={`node-${node.type}-${node.path}`}
          className={`
            flex items-center gap-2 px-2 py-1.5 cursor-pointer
            hover:bg-gray-800/50 transition-all
            border-l-2
            ${isSelected
              ? 'bg-blue-500/10 border-blue-500'
              : node.modified
                ? 'bg-yellow-500/5 border-transparent'
                : 'border-transparent'
            }
          `}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
          onClick={() => isDirectory ? handleDirectoryClick(node) : handleFileClick(node)}
          title={node.path}
        >
          {/* Chevron for directories with children */}
          {isDirectory && hasChildren && (
            <ChevronRight
              data-testid={`chevron-${node.path}`}
              className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
            />
          )}
          {/* Spacer for files and empty directories */}
          {(!isDirectory || !hasChildren) && <div className="w-4" />}

          {/* Icon */}
          {isDirectory ? (
            isExpanded ? (
              <FolderOpen
                data-testid={`icon-folder-open-${node.path}`}
                className="w-4 h-4 text-blue-400"
              />
            ) : (
              <Folder
                data-testid={`icon-folder-${node.path}`}
                className="w-4 h-4 text-blue-400"
              />
            )
          ) : (
            <File
              data-testid={`icon-file-${node.path}`}
              className="w-4 h-4 text-gray-400"
            />
          )}

          {/* Name */}
          <span
            data-testid={`name-${node.path}`}
            className={`flex-1 text-sm ${
              isSelected
                ? 'text-blue-400 font-medium'
                : node.modified
                  ? 'text-yellow-400'
                  : 'text-gray-300'
            }`}
          >
            {node.name}
          </span>

          {/* Modified indicator */}
          {node.modified && (
            <span
              data-testid={`modified-${node.path}`}
              className="text-xs font-bold text-yellow-400 bg-yellow-500/20 px-1.5 py-0.5 rounded"
            >
              M
            </span>
          )}
        </div>

        {/* Children */}
        {isDirectory && hasChildren && isExpanded && (
          <div>
            {node.children!.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  // Empty state
  if (!nodes || nodes.length === 0) {
    return (
      <div
        data-testid="file-tree"
        className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-gray-100"
      >
        <div data-testid="empty-tree" className="text-center text-gray-500 py-8">
          No files or folders to display
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="file-tree"
      className="bg-gray-900 border border-gray-800 rounded-lg p-2 text-gray-100"
    >
      {nodes.map((node) => renderNode(node))}
    </div>
  );
}
