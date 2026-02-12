/**
 * TestResultsSkeleton Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TestResultsSkeleton } from './TestResultsSkeleton';

describe('TestResultsSkeleton', () => {
  it('should render without errors', () => {
    render(<TestResultsSkeleton />);
    expect(screen.getByTestId('test-results-skeleton')).toBeInTheDocument();
  });

  it('should render default test count of 5', () => {
    const { container } = render(<TestResultsSkeleton />);
    const skeleton = screen.getByTestId('test-results-skeleton');

    // Find test items within the space-y-2 container
    const testContainer = skeleton.querySelector('.space-y-2');
    const testItems = testContainer?.querySelectorAll(':scope > .flex');

    expect(testItems?.length).toBe(5); // Default testCount
  });

  it('should render custom test count', () => {
    const { container } = render(<TestResultsSkeleton testCount={10} />);
    const skeleton = screen.getByTestId('test-results-skeleton');

    const testContainer = skeleton.querySelector('.space-y-2');
    const testItems = testContainer?.querySelectorAll(':scope > .flex');

    expect(testItems?.length).toBe(10);
  });

  it('should have summary header', () => {
    const { container } = render(<TestResultsSkeleton />);
    const header = container.querySelector('.p-4.bg-gray-800\\/50');

    expect(header).toBeInTheDocument();
  });

  it('should have stats footer', () => {
    const { container } = render(<TestResultsSkeleton />);

    // Find the last section with stats
    const allSections = container.querySelectorAll('.p-3.bg-gray-800\\/30');
    const footer = allSections[allSections.length - 1];

    expect(footer).toBeInTheDocument();
    // Should have 3 stat items
    const statItems = footer.querySelectorAll('.flex.items-center.gap-2');
    expect(statItems.length).toBe(3);
  });

  it('should apply custom className', () => {
    render(<TestResultsSkeleton className="my-tests" />);
    const skeleton = screen.getByTestId('test-results-skeleton');

    expect(skeleton).toHaveClass('my-tests');
  });

  it('should have animated placeholders', () => {
    const { container } = render(<TestResultsSkeleton />);
    const pulsingElements = container.querySelectorAll('.animate-pulse');

    expect(pulsingElements.length).toBeGreaterThan(5);
  });

  it('should have status icons for each test', () => {
    const { container } = render(<TestResultsSkeleton testCount={3} />);

    // Each test should have a circular status icon
    const testContainer = container.querySelector('.space-y-2');
    const statusIcons = testContainer?.querySelectorAll('.w-5.h-5.bg-gray-700.rounded-full');

    expect(statusIcons?.length).toBe(3);
  });
});
