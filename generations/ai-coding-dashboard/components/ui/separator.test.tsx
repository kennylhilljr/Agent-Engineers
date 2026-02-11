import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Separator } from './separator'

describe('Separator Component', () => {
  it('renders horizontal separator by default', () => {
    render(<Separator data-testid="separator" />)
    expect(screen.getByTestId('separator')).toBeInTheDocument()
  })

  it('renders vertical separator', () => {
    render(<Separator orientation="vertical" data-testid="separator" />)
    const separator = screen.getByTestId('separator')
    expect(separator).toBeInTheDocument()
    expect(separator).toHaveAttribute('data-orientation', 'vertical')
  })

  it('renders horizontal separator explicitly', () => {
    render(<Separator orientation="horizontal" data-testid="separator" />)
    const separator = screen.getByTestId('separator')
    expect(separator).toBeInTheDocument()
    expect(separator).toHaveAttribute('data-orientation', 'horizontal')
  })

  it('is decorative by default', () => {
    render(<Separator data-testid="separator" />)
    const separator = screen.getByTestId('separator')
    expect(separator).toHaveAttribute('role', 'none')
  })

  it('can be non-decorative', () => {
    render(<Separator decorative={false} data-testid="separator" />)
    const separator = screen.getByTestId('separator')
    expect(separator).toHaveAttribute('role', 'separator')
  })

  it('applies custom className', () => {
    render(<Separator className="custom-separator" data-testid="separator" />)
    expect(screen.getByTestId('separator')).toHaveClass('custom-separator')
  })
})
