/**
 * TaskCardSkeleton Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TaskCardSkeleton } from './TaskCardSkeleton';

describe('TaskCardSkeleton', () => {
  it('should render without errors', () => {
    render(<TaskCardSkeleton />);
    expect(screen.getByTestId('task-card-skeleton')).toBeInTheDocument();
  });

  it('should apply custom className', () => {
    render(<TaskCardSkeleton className="custom-class" />);
    const skeleton = screen.getByTestId('task-card-skeleton');
    expect(skeleton).toHaveClass('custom-class');
  });

  it('should have skeleton structure matching TaskCard', () => {
    render(<TaskCardSkeleton />);
    const skeleton = screen.getByTestId('task-card-skeleton');

    // Should have rounded corners and border
    expect(skeleton).toHaveClass('rounded-lg');
    expect(skeleton).toHaveClass('border-2');
    expect(skeleton).toHaveClass('border-gray-700');
  });

  it('should have multiple animated placeholders', () => {
    const { container } = render(<TaskCardSkeleton />);
    const animatedElements = container.querySelectorAll('.animate-pulse');

    // Should have multiple skeleton elements
    expect(animatedElements.length).toBeGreaterThan(3);
  });

  it('should have shimmer overlay for loading effect', () => {
    const { container } = render(<TaskCardSkeleton />);
    const shimmerElement = container.querySelector('.bg-gradient-to-r');

    expect(shimmerElement).toBeInTheDocument();
  });

  it('should match TaskCard dimensions', () => {
    const { container } = render(<TaskCardSkeleton />);
    const skeleton = screen.getByTestId('task-card-skeleton');

    // Should have same border and rounded structure
    expect(skeleton).toHaveClass('rounded-lg');
    expect(skeleton).toHaveClass('border-2');

    // Check for inner padding in sections
    const paddedSections = container.querySelectorAll('.p-4');
    expect(paddedSections.length).toBeGreaterThan(0);
  });
});
