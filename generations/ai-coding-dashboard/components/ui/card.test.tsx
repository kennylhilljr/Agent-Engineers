import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './card'

describe('Card Components', () => {
  it('renders Card component', () => {
    render(
      <Card data-testid="card">
        <p>Card content</p>
      </Card>
    )
    expect(screen.getByTestId('card')).toBeInTheDocument()
  })

  it('renders complete Card with all sub-components', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Test Title</CardTitle>
          <CardDescription>Test Description</CardDescription>
        </CardHeader>
        <CardContent>Test Content</CardContent>
        <CardFooter>Test Footer</CardFooter>
      </Card>
    )

    expect(screen.getByText('Test Title')).toBeInTheDocument()
    expect(screen.getByText('Test Description')).toBeInTheDocument()
    expect(screen.getByText('Test Content')).toBeInTheDocument()
    expect(screen.getByText('Test Footer')).toBeInTheDocument()
  })

  it('applies custom className to Card', () => {
    render(<Card className="custom-card" data-testid="card">Content</Card>)
    expect(screen.getByTestId('card')).toHaveClass('custom-card')
  })

  it('renders CardHeader with custom className', () => {
    render(<CardHeader className="custom-header" data-testid="header">Header</CardHeader>)
    expect(screen.getByTestId('header')).toHaveClass('custom-header')
  })
})
