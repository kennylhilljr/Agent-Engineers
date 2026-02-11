import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Badge } from './badge'

describe('Badge Component', () => {
  it('renders badge with text', () => {
    render(<Badge>New</Badge>)
    expect(screen.getByText('New')).toBeInTheDocument()
  })

  it('renders with default variant', () => {
    render(<Badge variant="default">Default</Badge>)
    expect(screen.getByText('Default')).toBeInTheDocument()
  })

  it('renders with secondary variant', () => {
    render(<Badge variant="secondary">Secondary</Badge>)
    expect(screen.getByText('Secondary')).toBeInTheDocument()
  })

  it('renders with destructive variant', () => {
    render(<Badge variant="destructive">Destructive</Badge>)
    expect(screen.getByText('Destructive')).toBeInTheDocument()
  })

  it('renders with outline variant', () => {
    render(<Badge variant="outline">Outline</Badge>)
    expect(screen.getByText('Outline')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    render(<Badge className="custom-badge" data-testid="badge">Badge</Badge>)
    const badge = screen.getByTestId('badge')
    expect(badge).toHaveClass('custom-badge')
  })

  it('renders with children content', () => {
    render(
      <Badge>
        <span>Complex</span> Content
      </Badge>
    )
    expect(screen.getByText('Complex')).toBeInTheDocument()
    expect(screen.getByText(/Content/)).toBeInTheDocument()
  })
})
