import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Home from './page';

describe('Home Page', () => {
  it('renders the main heading', () => {
    render(<Home />);
    const heading = screen.getByText('AI Coding Dashboard');
    expect(heading).toBeInTheDocument();
  });

  it('displays Next.js 14 feature card', () => {
    render(<Home />);
    const nextjsCard = screen.getByText('Next.js 14');
    expect(nextjsCard).toBeInTheDocument();
  });

  it('displays Tailwind CSS feature card', () => {
    render(<Home />);
    const tailwindCard = screen.getByText('Tailwind CSS');
    expect(tailwindCard).toBeInTheDocument();
  });

  it('displays CopilotKit feature card', () => {
    render(<Home />);
    const copilotCard = screen.getByText('CopilotKit');
    expect(copilotCard).toBeInTheDocument();
  });

  it('displays TypeScript feature card', () => {
    render(<Home />);
    const typescriptCard = screen.getByText('TypeScript');
    expect(typescriptCard).toBeInTheDocument();
  });

  it('has dark theme background', () => {
    const { container } = render(<Home />);
    const main = container.querySelector('main');
    expect(main).toHaveClass('bg-gray-900');
  });

  it('has proper text color for dark theme', () => {
    const { container } = render(<Home />);
    const main = container.querySelector('main');
    expect(main).toHaveClass('text-white');
  });
});
