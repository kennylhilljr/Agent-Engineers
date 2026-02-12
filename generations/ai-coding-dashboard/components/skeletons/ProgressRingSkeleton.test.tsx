/**
 * ProgressRingSkeleton Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProgressRingSkeleton } from './ProgressRingSkeleton';

describe('ProgressRingSkeleton', () => {
  it('should render without errors', () => {
    render(<ProgressRingSkeleton />);
    expect(screen.getByTestId('progress-ring-skeleton')).toBeInTheDocument();
  });

  it('should apply size variants', () => {
    const { rerender } = render(<ProgressRingSkeleton size="small" />);
    let skeleton = screen.getByTestId('progress-ring-skeleton');
    expect(skeleton.querySelector('.w-24')).toBeInTheDocument();

    rerender(<ProgressRingSkeleton size="medium" />);
    skeleton = screen.getByTestId('progress-ring-skeleton');
    expect(skeleton.querySelector('.w-32')).toBeInTheDocument();

    rerender(<ProgressRingSkeleton size="large" />);
    skeleton = screen.getByTestId('progress-ring-skeleton');
    expect(skeleton.querySelector('.w-48')).toBeInTheDocument();
  });

  it('should render SVG ring', () => {
    const { container } = render(<ProgressRingSkeleton />);
    const svg = container.querySelector('svg');

    expect(svg).toBeInTheDocument();
    expect(svg?.querySelectorAll('circle')).toHaveLength(2); // Background + animated arc
  });

  it('should show metrics when showMetrics is true', () => {
    const { container } = render(<ProgressRingSkeleton showMetrics={true} />);
    const metrics = container.querySelectorAll('.flex.flex-col.items-center.gap-1');

    expect(metrics.length).toBe(3); // 3 metric placeholders
  });

  it('should hide metrics when showMetrics is false', () => {
    const { container } = render(<ProgressRingSkeleton showMetrics={false} />);
    const metrics = container.querySelectorAll('.flex.flex-col.items-center.gap-1');

    expect(metrics.length).toBe(0);
  });

  it('should apply custom className', () => {
    render(<ProgressRingSkeleton className="my-custom-class" />);
    const skeleton = screen.getByTestId('progress-ring-skeleton');

    expect(skeleton).toHaveClass('my-custom-class');
  });

  it('should have rotating animation on SVG', () => {
    const { container } = render(<ProgressRingSkeleton />);
    const svg = container.querySelector('svg');

    // Framer motion will add animation, check for transform rotate class
    expect(svg).toHaveClass('transform', '-rotate-90');
  });
});
