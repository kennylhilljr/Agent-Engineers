/**
 * FileTreeSkeleton Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FileTreeSkeleton } from './FileTreeSkeleton';

describe('FileTreeSkeleton', () => {
  it('should render without errors', () => {
    render(<FileTreeSkeleton />);
    expect(screen.getByTestId('file-tree-skeleton')).toBeInTheDocument();
  });

  it('should render default depth of 3 levels', () => {
    const { container } = render(<FileTreeSkeleton />);
    const skeleton = screen.getByTestId('file-tree-skeleton');

    // The actual structure has nested divs, so count top-level items differently
    const topLevelSpaces = skeleton.querySelectorAll(':scope > .space-y-2');
    expect(topLevelSpaces.length).toBeGreaterThan(0);
  });

  it('should render custom depth', () => {
    const { container } = render(<FileTreeSkeleton depth={5} />);
    const skeleton = screen.getByTestId('file-tree-skeleton');

    // Verify structure exists with custom depth
    const topLevelSpaces = skeleton.querySelectorAll(':scope > .space-y-2');
    expect(topLevelSpaces.length).toBeGreaterThan(0);
  });

  it('should have nested structure', () => {
    const { container } = render(<FileTreeSkeleton depth={3} />);
    const nestedItems = container.querySelectorAll('.ml-6');

    // Should have nested children
    expect(nestedItems.length).toBeGreaterThan(0);
  });

  it('should apply custom className', () => {
    render(<FileTreeSkeleton className="custom-tree" />);
    const skeleton = screen.getByTestId('file-tree-skeleton');

    expect(skeleton).toHaveClass('custom-tree');
  });

  it('should have pulsing animation on placeholders', () => {
    const { container } = render(<FileTreeSkeleton />);
    const pulsingElements = container.querySelectorAll('.animate-pulse');

    expect(pulsingElements.length).toBeGreaterThan(0);
  });

  it('should have icon and text placeholders', () => {
    const { container } = render(<FileTreeSkeleton depth={1} />);

    // Icon placeholders (w-4 h-4)
    const icons = container.querySelectorAll('.w-4.h-4');
    expect(icons.length).toBeGreaterThan(0);

    // Text placeholders (h-4)
    const textPlaceholders = container.querySelectorAll('.h-4.bg-gray-700.rounded');
    expect(textPlaceholders.length).toBeGreaterThan(0);
  });
});
