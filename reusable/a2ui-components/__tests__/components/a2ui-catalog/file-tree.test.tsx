/**
 * FileTree Component Unit Tests
 * Comprehensive test suite for FileTree component
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { FileTree } from '@/components/a2ui-catalog/file-tree';
import { A2UIProps, FileTreeData, FileNode } from '@/lib/a2ui-types';

describe('FileTree Component', () => {
  describe('Basic Rendering', () => {
    test('renders with minimal props', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByTestId('file-tree')).toBeInTheDocument();
    });

    test('renders empty state when no nodes provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByTestId('empty-tree')).toBeInTheDocument();
      expect(screen.getByText('No files or folders to display')).toBeInTheDocument();
    });

    test('renders single file node', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText('index.ts')).toBeInTheDocument();
      expect(screen.getByTestId('icon-file-/src/index.ts')).toBeInTheDocument();
    });

    test('renders single directory node', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText('src')).toBeInTheDocument();
      expect(screen.getByTestId('icon-folder-/src')).toBeInTheDocument();
    });

    test('renders multiple root nodes', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
            },
            {
              path: '/package.json',
              name: 'package.json',
              type: 'file',
            },
            {
              path: '/README.md',
              name: 'README.md',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText('src')).toBeInTheDocument();
      expect(screen.getByText('package.json')).toBeInTheDocument();
      expect(screen.getByText('README.md')).toBeInTheDocument();
    });
  });

  describe('File and Directory Icons', () => {
    test('displays file icon for file nodes', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/test.js',
              name: 'test.js',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByTestId('icon-file-/test.js')).toBeInTheDocument();
    });

    test('displays folder icon for collapsed directory', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/components',
              name: 'components',
              type: 'directory',
              children: [
                {
                  path: '/components/Button.tsx',
                  name: 'Button.tsx',
                  type: 'file',
                },
              ],
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByTestId('icon-folder-/components')).toBeInTheDocument();
    });

    test('displays open folder icon for expanded directory', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/components',
              name: 'components',
              type: 'directory',
              children: [
                {
                  path: '/components/Button.tsx',
                  name: 'Button.tsx',
                  type: 'file',
                },
              ],
            },
          ],
          expandedPaths: ['/components'],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByTestId('icon-folder-open-/components')).toBeInTheDocument();
    });
  });

  describe('Nested Folder Structure', () => {
    test('renders nested children when directory is expanded', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [
                {
                  path: '/src/components',
                  name: 'components',
                  type: 'directory',
                  children: [
                    {
                      path: '/src/components/Button.tsx',
                      name: 'Button.tsx',
                      type: 'file',
                    },
                  ],
                },
                {
                  path: '/src/index.ts',
                  name: 'index.ts',
                  type: 'file',
                },
              ],
            },
          ],
          expandedPaths: ['/src', '/src/components'],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText('components')).toBeInTheDocument();
      expect(screen.getByText('Button.tsx')).toBeInTheDocument();
      expect(screen.getByText('index.ts')).toBeInTheDocument();
    });

    test('hides nested children when directory is collapsed', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [
                {
                  path: '/src/index.ts',
                  name: 'index.ts',
                  type: 'file',
                },
              ],
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.queryByText('index.ts')).not.toBeInTheDocument();
    });

    test('renders deeply nested structure', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/a',
              name: 'a',
              type: 'directory',
              children: [
                {
                  path: '/a/b',
                  name: 'b',
                  type: 'directory',
                  children: [
                    {
                      path: '/a/b/c',
                      name: 'c',
                      type: 'directory',
                      children: [
                        {
                          path: '/a/b/c/file.txt',
                          name: 'file.txt',
                          type: 'file',
                        },
                      ],
                    },
                  ],
                },
              ],
            },
          ],
          expandedPaths: ['/a', '/a/b', '/a/b/c'],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText('a')).toBeInTheDocument();
      expect(screen.getByText('b')).toBeInTheDocument();
      expect(screen.getByText('c')).toBeInTheDocument();
      expect(screen.getByText('file.txt')).toBeInTheDocument();
    });
  });

  describe('Expand/Collapse Functionality', () => {
    test('displays chevron icon for directories with children', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [
                {
                  path: '/src/index.ts',
                  name: 'index.ts',
                  type: 'file',
                },
              ],
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByTestId('chevron-/src')).toBeInTheDocument();
    });

    test('clicking directory expands it', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [
                {
                  path: '/src/index.ts',
                  name: 'index.ts',
                  type: 'file',
                },
              ],
            },
          ],
        },
      };

      render(<FileTree {...props} />);

      // Initially collapsed
      expect(screen.queryByText('index.ts')).not.toBeInTheDocument();

      // Click to expand
      const directoryNode = screen.getByTestId('node-directory-/src');
      fireEvent.click(directoryNode);

      // Now expanded
      expect(screen.getByText('index.ts')).toBeInTheDocument();
    });

    test('clicking directory collapses it', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [
                {
                  path: '/src/index.ts',
                  name: 'index.ts',
                  type: 'file',
                },
              ],
            },
          ],
          expandedPaths: ['/src'],
        },
      };

      render(<FileTree {...props} />);

      // Initially expanded
      expect(screen.getByText('index.ts')).toBeInTheDocument();

      // Click to collapse
      const directoryNode = screen.getByTestId('node-directory-/src');
      fireEvent.click(directoryNode);

      // Now collapsed
      expect(screen.queryByText('index.ts')).not.toBeInTheDocument();
    });

    test('chevron rotates when directory is expanded', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [
                {
                  path: '/src/index.ts',
                  name: 'index.ts',
                  type: 'file',
                },
              ],
            },
          ],
        },
      };

      render(<FileTree {...props} />);

      const chevron = screen.getByTestId('chevron-/src');

      // Initially not rotated
      expect(chevron).not.toHaveClass('rotate-90');

      // Click to expand
      const directoryNode = screen.getByTestId('node-directory-/src');
      fireEvent.click(directoryNode);

      // Now rotated
      expect(chevron).toHaveClass('rotate-90');
    });
  });

  describe('Modified Files Highlighting', () => {
    test('displays modified indicator for modified files', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
              modified: true,
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByTestId('modified-/src/index.ts')).toBeInTheDocument();
      expect(screen.getByText('M')).toBeInTheDocument();
    });

    test('applies yellow background for modified files', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
              modified: true,
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      const node = screen.getByTestId('node-file-/src/index.ts');
      expect(node).toHaveClass('bg-yellow-500/5');
    });

    test('applies yellow text color for modified file names', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
              modified: true,
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      const name = screen.getByTestId('name-/src/index.ts');
      expect(name).toHaveClass('text-yellow-400');
    });

    test('does not display modified indicator for unmodified files', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
              modified: false,
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.queryByTestId('modified-/src/index.ts')).not.toBeInTheDocument();
    });

    test('handles modified directories', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              modified: true,
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByTestId('modified-/src')).toBeInTheDocument();
    });
  });

  describe('Selection State', () => {
    test('highlights selected file', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
            },
          ],
          selectedPath: '/src/index.ts',
        },
      };

      render(<FileTree {...props} />);
      const node = screen.getByTestId('node-file-/src/index.ts');
      expect(node).toHaveClass('bg-blue-500/10', 'border-blue-500');
    });

    test('clicking file selects it', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);

      const fileNode = screen.getByTestId('node-file-/src/index.ts');
      fireEvent.click(fileNode);

      expect(fileNode).toHaveClass('bg-blue-500/10');
    });

    test('selected file name has blue text color', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
            },
          ],
          selectedPath: '/src/index.ts',
        },
      };

      render(<FileTree {...props} />);
      const name = screen.getByTestId('name-/src/index.ts');
      expect(name).toHaveClass('text-blue-400');
    });
  });

  describe('Event Handling', () => {
    test('calls onEvent when file is clicked', () => {
      const mockOnEvent = jest.fn();
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
            },
          ],
        },
        onEvent: mockOnEvent,
      };

      render(<FileTree {...props} />);
      const fileNode = screen.getByTestId('node-file-/src/index.ts');
      fireEvent.click(fileNode);

      expect(mockOnEvent).toHaveBeenCalledWith(
        'click',
        expect.objectContaining({
          path: '/src/index.ts',
        })
      );
    });

    test('calls onEvent when directory is expanded', () => {
      const mockOnEvent = jest.fn();
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [
                {
                  path: '/src/index.ts',
                  name: 'index.ts',
                  type: 'file',
                },
              ],
            },
          ],
        },
        onEvent: mockOnEvent,
      };

      render(<FileTree {...props} />);
      const directoryNode = screen.getByTestId('node-directory-/src');
      fireEvent.click(directoryNode);

      expect(mockOnEvent).toHaveBeenCalledWith(
        'expand',
        expect.objectContaining({
          path: '/src',
          expanded: true,
        })
      );
    });

    test('calls onEvent when directory is collapsed', () => {
      const mockOnEvent = jest.fn();
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [
                {
                  path: '/src/index.ts',
                  name: 'index.ts',
                  type: 'file',
                },
              ],
            },
          ],
          expandedPaths: ['/src'],
        },
        onEvent: mockOnEvent,
      };

      render(<FileTree {...props} />);
      const directoryNode = screen.getByTestId('node-directory-/src');
      fireEvent.click(directoryNode);

      expect(mockOnEvent).toHaveBeenCalledWith(
        'expand',
        expect.objectContaining({
          path: '/src',
          expanded: false,
        })
      );
    });

    test('does not throw error when onEvent is not provided', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      const fileNode = screen.getByTestId('node-file-/src/index.ts');

      expect(() => {
        fireEvent.click(fileNode);
      }).not.toThrow();
    });
  });

  describe('Tooltips and Accessibility', () => {
    test('displays file path in title attribute', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/components/Button.tsx',
              name: 'Button.tsx',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      const node = screen.getByTestId('node-file-/src/components/Button.tsx');
      expect(node).toHaveAttribute('title', '/src/components/Button.tsx');
    });

    test('node has cursor pointer styling', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src/index.ts',
              name: 'index.ts',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      const node = screen.getByTestId('node-file-/src/index.ts');
      expect(node).toHaveClass('cursor-pointer');
    });
  });

  describe('Dark Theme Styling', () => {
    test('applies dark theme background', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [],
        },
      };

      render(<FileTree {...props} />);
      const tree = screen.getByTestId('file-tree');
      expect(tree).toHaveClass('bg-gray-900', 'border-gray-800', 'text-gray-100');
    });

    test('files have gray text color', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/test.ts',
              name: 'test.ts',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      const name = screen.getByTestId('name-/test.ts');
      expect(name).toHaveClass('text-gray-300');
    });

    test('directories have blue icons', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      const icon = screen.getByTestId('icon-folder-/src');
      expect(icon).toHaveClass('text-blue-400');
    });

    test('files have gray icons', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/test.ts',
              name: 'test.ts',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      const icon = screen.getByTestId('icon-file-/test.ts');
      expect(icon).toHaveClass('text-gray-400');
    });
  });

  describe('Edge Cases', () => {
    test('handles empty children array', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [],
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText('src')).toBeInTheDocument();
      expect(screen.queryByTestId('chevron-/src')).not.toBeInTheDocument();
    });

    test('handles undefined children', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText('src')).toBeInTheDocument();
      expect(screen.queryByTestId('chevron-/src')).not.toBeInTheDocument();
    });

    test('handles single file in tree', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/README.md',
              name: 'README.md',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText('README.md')).toBeInTheDocument();
    });

    test('handles deeply nested single file path', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/src',
              name: 'src',
              type: 'directory',
              children: [
                {
                  path: '/src/components',
                  name: 'components',
                  type: 'directory',
                  children: [
                    {
                      path: '/src/components/ui',
                      name: 'ui',
                      type: 'directory',
                      children: [
                        {
                          path: '/src/components/ui/button',
                          name: 'button',
                          type: 'directory',
                          children: [
                            {
                              path: '/src/components/ui/button/Button.tsx',
                              name: 'Button.tsx',
                              type: 'file',
                            },
                          ],
                        },
                      ],
                    },
                  ],
                },
              ],
            },
          ],
          expandedPaths: ['/src', '/src/components', '/src/components/ui', '/src/components/ui/button'],
        },
      };

      render(<FileTree {...props} />);
      expect(screen.getByText('Button.tsx')).toBeInTheDocument();
    });
  });

  describe('Hover Effects', () => {
    test('applies hover styles to nodes', () => {
      const props: A2UIProps = {
        type: 'a2ui.FileTree',
        data: {
          nodes: [
            {
              path: '/test.ts',
              name: 'test.ts',
              type: 'file',
            },
          ],
        },
      };

      render(<FileTree {...props} />);
      const node = screen.getByTestId('node-file-/test.ts');
      expect(node).toHaveClass('hover:bg-gray-800/50', 'transition-all');
    });
  });
});
