import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mock Next.js font module
vi.mock('next/font/google', () => ({
  Inter: () => ({
    className: 'font-inter',
  }),
}));

import RootLayout from './layout';

describe('RootLayout', () => {
  it('renders children correctly', () => {
    const { container } = render(
      <RootLayout>
        <div data-testid="test-child">Test Content</div>
      </RootLayout>
    );

    const child = container.querySelector('[data-testid="test-child"]');
    expect(child).toBeInTheDocument();
    expect(child?.textContent).toBe('Test Content');
  });

  it('has html element with lang="en"', () => {
    const { container } = render(
      <RootLayout>
        <div>Test</div>
      </RootLayout>
    );

    const html = container.querySelector('html');
    expect(html).toHaveAttribute('lang', 'en');
  });

  it('has dark class on html element', () => {
    const { container } = render(
      <RootLayout>
        <div>Test</div>
      </RootLayout>
    );

    const html = container.querySelector('html');
    expect(html).toHaveClass('dark');
  });

  it('applies Inter font class to body', () => {
    const { container } = render(
      <RootLayout>
        <div>Test</div>
      </RootLayout>
    );

    const body = container.querySelector('body');
    expect(body).toBeInTheDocument();
  });
});
