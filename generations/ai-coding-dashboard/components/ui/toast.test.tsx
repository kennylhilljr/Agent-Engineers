import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import {
  Toast,
  ToastAction,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from './toast'

describe('Toast Component', () => {
  it('renders toast with title and description', () => {
    render(
      <ToastProvider>
        <Toast open={true}>
          <ToastTitle>Toast Title</ToastTitle>
          <ToastDescription>Toast Description</ToastDescription>
        </Toast>
        <ToastViewport />
      </ToastProvider>
    )

    expect(screen.getByText('Toast Title')).toBeInTheDocument()
    expect(screen.getByText('Toast Description')).toBeInTheDocument()
  })

  it('renders toast with default variant', () => {
    render(
      <ToastProvider>
        <Toast variant="default" open={true}>
          <ToastTitle>Default Toast</ToastTitle>
        </Toast>
        <ToastViewport />
      </ToastProvider>
    )

    expect(screen.getByText('Default Toast')).toBeInTheDocument()
  })

  it('renders toast with destructive variant', () => {
    render(
      <ToastProvider>
        <Toast variant="destructive" open={true}>
          <ToastTitle>Error Toast</ToastTitle>
        </Toast>
        <ToastViewport />
      </ToastProvider>
    )

    expect(screen.getByText('Error Toast')).toBeInTheDocument()
  })

  it('renders toast action', () => {
    render(
      <ToastProvider>
        <Toast open={true}>
          <ToastTitle>Title</ToastTitle>
          <ToastAction altText="Undo">Undo</ToastAction>
        </Toast>
        <ToastViewport />
      </ToastProvider>
    )

    expect(screen.getByText('Undo')).toBeInTheDocument()
  })

  it('renders toast close button', () => {
    render(
      <ToastProvider>
        <Toast open={true}>
          <ToastTitle>Title</ToastTitle>
          <ToastClose />
        </Toast>
        <ToastViewport />
      </ToastProvider>
    )

    expect(screen.getByText('Title')).toBeInTheDocument()
    // Close button should be present (has sr-only text "Close")
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('renders ToastViewport', () => {
    const { container } = render(
      <ToastProvider>
        <ToastViewport data-testid="viewport" />
      </ToastProvider>
    )

    expect(container.querySelector('[data-testid="viewport"]')).toBeInTheDocument()
  })
})
