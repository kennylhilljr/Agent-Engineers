import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import {
  A2UIRenderer,
  a2uiCatalog,
  hasA2UIComponent,
  getA2UIComponentNames,
  Button,
  Card,
  Text,
  Input,
  Container,
  Grid,
  Badge,
  Divider,
} from './a2ui-catalog';

describe('A2UI Catalog', () => {
  describe('Catalog Structure', () => {
    it('should contain all expected components', () => {
      const expectedComponents = [
        'a2ui.Button',
        'a2ui.Card',
        'a2ui.Text',
        'a2ui.Input',
        'a2ui.Container',
        'a2ui.Grid',
        'a2ui.Badge',
        'a2ui.Divider',
      ];

      expectedComponents.forEach((componentName) => {
        expect(a2uiCatalog).toHaveProperty(componentName);
        expect(typeof a2uiCatalog[componentName]).toBe('function');
      });
    });

    it('should have correct number of components', () => {
      const componentCount = Object.keys(a2uiCatalog).length;
      expect(componentCount).toBe(8);
    });
  });

  describe('Helper Functions', () => {
    it('hasA2UIComponent should return true for existing components', () => {
      expect(hasA2UIComponent('a2ui.Button')).toBe(true);
      expect(hasA2UIComponent('a2ui.Card')).toBe(true);
      expect(hasA2UIComponent('a2ui.Text')).toBe(true);
    });

    it('hasA2UIComponent should return false for non-existing components', () => {
      expect(hasA2UIComponent('a2ui.NonExistent')).toBe(false);
      expect(hasA2UIComponent('Button')).toBe(false);
      expect(hasA2UIComponent('')).toBe(false);
    });

    it('getA2UIComponentNames should return all component names', () => {
      const names = getA2UIComponentNames();
      expect(names).toBeInstanceOf(Array);
      expect(names.length).toBe(8);
      expect(names).toContain('a2ui.Button');
      expect(names).toContain('a2ui.Card');
      expect(names).toContain('a2ui.Text');
    });
  });

  describe('A2UIRenderer', () => {
    it('should render Button component from catalog', () => {
      render(
        <A2UIRenderer component="a2ui.Button">
          Click Me
        </A2UIRenderer>
      );

      const button = screen.getByText('Click Me');
      expect(button).toBeInTheDocument();
      expect(button.tagName).toBe('BUTTON');
    });

    it('should render Card component from catalog', () => {
      render(
        <A2UIRenderer component="a2ui.Card" props={{ title: 'Test Card' }}>
          Card Content
        </A2UIRenderer>
      );

      expect(screen.getByText('Test Card')).toBeInTheDocument();
      expect(screen.getByText('Card Content')).toBeInTheDocument();
    });

    it('should render Text component from catalog', () => {
      render(
        <A2UIRenderer component="a2ui.Text" props={{ variant: 'h1' }}>
          Test Heading
        </A2UIRenderer>
      );

      const heading = screen.getByText('Test Heading');
      expect(heading).toBeInTheDocument();
      expect(heading.tagName).toBe('H1');
    });

    it('should pass props correctly to components', () => {
      const handleClick = vi.fn();
      render(
        <A2UIRenderer
          component="a2ui.Button"
          props={{ onClick: handleClick, variant: 'secondary' }}
        >
          Click Me
        </A2UIRenderer>
      );

      const button = screen.getByText('Click Me');
      fireEvent.click(button);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('should render error message for non-existent component', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      render(
        <A2UIRenderer component="a2ui.NonExistent">
          Content
        </A2UIRenderer>
      );

      expect(screen.getByText(/Component "a2ui.NonExistent" not found/i)).toBeInTheDocument();
      expect(consoleSpy).toHaveBeenCalledWith('A2UI component "a2ui.NonExistent" not found in catalog');

      consoleSpy.mockRestore();
    });

    it('should handle missing props gracefully', () => {
      render(<A2UIRenderer component="a2ui.Button" />);
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should render nested components', () => {
      render(
        <A2UIRenderer component="a2ui.Card" props={{ title: 'Parent' }}>
          <A2UIRenderer component="a2ui.Text">
            Nested Text
          </A2UIRenderer>
        </A2UIRenderer>
      );

      expect(screen.getByText('Parent')).toBeInTheDocument();
      expect(screen.getByText('Nested Text')).toBeInTheDocument();
    });
  });

  describe('Button Component', () => {
    it('should render with default props', () => {
      render(<Button>Default Button</Button>);
      const button = screen.getByText('Default Button');
      expect(button).toBeInTheDocument();
      expect(button).not.toBeDisabled();
    });

    it('should apply variant classes', () => {
      const { rerender } = render(<Button variant="primary">Primary</Button>);
      expect(screen.getByText('Primary')).toHaveClass('bg-blue-600');

      rerender(<Button variant="secondary">Secondary</Button>);
      expect(screen.getByText('Secondary')).toHaveClass('bg-gray-600');

      rerender(<Button variant="danger">Danger</Button>);
      expect(screen.getByText('Danger')).toHaveClass('bg-red-600');
    });

    it('should handle click events', () => {
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Clickable</Button>);

      fireEvent.click(screen.getByText('Clickable'));
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('should be disabled when disabled prop is true', () => {
      render(<Button disabled>Disabled Button</Button>);
      const button = screen.getByText('Disabled Button');
      expect(button).toBeDisabled();
    });
  });

  describe('Card Component', () => {
    it('should render without title', () => {
      render(<Card>Card content</Card>);
      expect(screen.getByText('Card content')).toBeInTheDocument();
    });

    it('should render with title', () => {
      render(<Card title="Card Title">Card content</Card>);
      expect(screen.getByText('Card Title')).toBeInTheDocument();
      expect(screen.getByText('Card content')).toBeInTheDocument();
    });

    it('should apply custom className', () => {
      const { container } = render(<Card className="custom-class">Content</Card>);
      const card = container.firstChild;
      expect(card).toHaveClass('custom-class');
    });
  });

  describe('Text Component', () => {
    it('should render different heading variants', () => {
      const { rerender } = render(<Text variant="h1">Heading 1</Text>);
      expect(screen.getByText('Heading 1').tagName).toBe('H1');

      rerender(<Text variant="h2">Heading 2</Text>);
      expect(screen.getByText('Heading 2').tagName).toBe('H2');

      rerender(<Text variant="h3">Heading 3</Text>);
      expect(screen.getByText('Heading 3').tagName).toBe('H3');

      rerender(<Text variant="h4">Heading 4</Text>);
      expect(screen.getByText('Heading 4').tagName).toBe('H4');
    });

    it('should render body text as paragraph by default', () => {
      render(<Text>Body text</Text>);
      expect(screen.getByText('Body text').tagName).toBe('P');
    });

    it('should apply variant classes', () => {
      render(<Text variant="caption">Caption text</Text>);
      expect(screen.getByText('Caption text')).toHaveClass('text-xs');
    });
  });

  describe('Input Component', () => {
    it('should render with default type', () => {
      render(<Input placeholder="Enter text" />);
      const input = screen.getByPlaceholderText('Enter text');
      expect(input).toBeInTheDocument();
      expect(input).toHaveAttribute('type', 'text');
    });

    it('should handle value and onChange', () => {
      const handleChange = vi.fn();
      render(<Input value="test value" onChange={handleChange} />);

      const input = screen.getByDisplayValue('test value');
      fireEvent.change(input, { target: { value: 'new value' } });
      expect(handleChange).toHaveBeenCalled();
    });

    it('should support different input types', () => {
      const { rerender } = render(<Input type="email" />);
      expect(screen.getByRole('textbox')).toHaveAttribute('type', 'email');

      rerender(<Input type="password" />);
      const passwordInput = document.querySelector('input[type="password"]');
      expect(passwordInput).toBeInTheDocument();
    });
  });

  describe('Container Component', () => {
    it('should render children', () => {
      render(<Container>Container content</Container>);
      expect(screen.getByText('Container content')).toBeInTheDocument();
    });

    it('should apply maxWidth prop', () => {
      const { container } = render(<Container maxWidth="max-w-4xl">Content</Container>);
      expect(container.firstChild).toHaveClass('max-w-4xl');
    });
  });

  describe('Grid Component', () => {
    it('should render grid with children', () => {
      render(
        <Grid>
          <div>Item 1</div>
          <div>Item 2</div>
        </Grid>
      );
      expect(screen.getByText('Item 1')).toBeInTheDocument();
      expect(screen.getByText('Item 2')).toBeInTheDocument();
    });

    it('should apply cols and gap props', () => {
      const { container } = render(<Grid cols="3" gap="6">Content</Grid>);
      expect(container.firstChild).toHaveClass('grid-cols-3');
      expect(container.firstChild).toHaveClass('gap-6');
    });
  });

  describe('Badge Component', () => {
    it('should render badge with default variant', () => {
      render(<Badge>Default Badge</Badge>);
      const badge = screen.getByText('Default Badge');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveClass('bg-gray-600');
    });

    it('should apply variant classes', () => {
      const { rerender } = render(<Badge variant="success">Success</Badge>);
      expect(screen.getByText('Success')).toHaveClass('bg-green-600');

      rerender(<Badge variant="error">Error</Badge>);
      expect(screen.getByText('Error')).toHaveClass('bg-red-600');

      rerender(<Badge variant="warning">Warning</Badge>);
      expect(screen.getByText('Warning')).toHaveClass('bg-yellow-600');
    });
  });

  describe('Divider Component', () => {
    it('should render horizontal rule', () => {
      const { container } = render(<Divider />);
      const hr = container.querySelector('hr');
      expect(hr).toBeInTheDocument();
    });

    it('should apply custom className', () => {
      const { container } = render(<Divider className="my-8" />);
      const hr = container.querySelector('hr');
      expect(hr).toHaveClass('my-8');
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty children', () => {
      render(<A2UIRenderer component="a2ui.Button" />);
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should handle undefined props', () => {
      const { container } = render(<A2UIRenderer component="a2ui.Card" props={undefined} />);
      const card = container.querySelector('.border-gray-700');
      expect(card).toBeInTheDocument();
    });

    it('should handle special characters in text', () => {
      render(<Text>Special &lt;&gt; &amp; characters</Text>);
      expect(screen.getByText(/Special.*characters/)).toBeInTheDocument();
    });

    it('should handle multiple className props', () => {
      render(<Button className="custom-1 custom-2">Button</Button>);
      const button = screen.getByText('Button');
      expect(button).toHaveClass('custom-1');
      expect(button).toHaveClass('custom-2');
    });
  });
});
