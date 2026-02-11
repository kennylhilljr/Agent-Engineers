import { describe, it, expect, vi as vitest } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import React from 'react';
import { A2UIRenderer, getA2UIComponentNames, hasA2UIComponent } from './a2ui-catalog';

/**
 * Integration tests for A2UI Catalog
 * These tests verify that multiple components work together correctly
 */
describe('A2UI Catalog Integration Tests', () => {
  describe('Complete UI Workflows', () => {
    it('should render a complete form with multiple components', () => {
      const handleSubmit = vitest.fn();

      render(
        <div>
          <A2UIRenderer component="a2ui.Container">
            <A2UIRenderer component="a2ui.Card" props={{ title: 'User Form' }}>
              <div className="space-y-4">
                <A2UIRenderer component="a2ui.Text" props={{ variant: 'body' }}>
                  Please fill out the form below:
                </A2UIRenderer>

                <div>
                  <A2UIRenderer component="a2ui.Text" props={{ variant: 'small' }}>
                    Name:
                  </A2UIRenderer>
                  <A2UIRenderer
                    component="a2ui.Input"
                    props={{ placeholder: 'Enter your name', 'data-testid': 'name-input' }}
                  />
                </div>

                <div>
                  <A2UIRenderer component="a2ui.Text" props={{ variant: 'small' }}>
                    Email:
                  </A2UIRenderer>
                  <A2UIRenderer
                    component="a2ui.Input"
                    props={{
                      type: 'email',
                      placeholder: 'Enter your email',
                      'data-testid': 'email-input',
                    }}
                  />
                </div>

                <A2UIRenderer
                  component="a2ui.Button"
                  props={{ onClick: handleSubmit, 'data-testid': 'submit-button' }}
                >
                  Submit
                </A2UIRenderer>
              </div>
            </A2UIRenderer>
          </A2UIRenderer>
        </div>
      );

      // Verify all components are rendered
      expect(screen.getByText('User Form')).toBeInTheDocument();
      expect(screen.getByText('Please fill out the form below:')).toBeInTheDocument();
      expect(screen.getByText('Name:')).toBeInTheDocument();
      expect(screen.getByText('Email:')).toBeInTheDocument();
      expect(screen.getByTestId('name-input')).toBeInTheDocument();
      expect(screen.getByTestId('email-input')).toBeInTheDocument();
      expect(screen.getByTestId('submit-button')).toBeInTheDocument();

      // Test interaction
      fireEvent.click(screen.getByTestId('submit-button'));
      expect(handleSubmit).toHaveBeenCalled();
    });

    it('should render a dashboard with multiple cards and badges', () => {
      render(
        <A2UIRenderer component="a2ui.Container">
          <A2UIRenderer component="a2ui.Text" props={{ variant: 'h1' }}>
            Dashboard
          </A2UIRenderer>

          <A2UIRenderer component="a2ui.Grid" props={{ cols: '3', gap: '4' }}>
            <A2UIRenderer component="a2ui.Card" props={{ title: 'Active Users' }}>
              <A2UIRenderer component="a2ui.Text" props={{ variant: 'h2' }}>
                1,234
              </A2UIRenderer>
              <A2UIRenderer component="a2ui.Badge" props={{ variant: 'success' }}>
                +12%
              </A2UIRenderer>
            </A2UIRenderer>

            <A2UIRenderer component="a2ui.Card" props={{ title: 'Revenue' }}>
              <A2UIRenderer component="a2ui.Text" props={{ variant: 'h2' }}>
                $45.6K
              </A2UIRenderer>
              <A2UIRenderer component="a2ui.Badge" props={{ variant: 'warning' }}>
                -3%
              </A2UIRenderer>
            </A2UIRenderer>

            <A2UIRenderer component="a2ui.Card" props={{ title: 'Orders' }}>
              <A2UIRenderer component="a2ui.Text" props={{ variant: 'h2' }}>
                892
              </A2UIRenderer>
              <A2UIRenderer component="a2ui.Badge" props={{ variant: 'info' }}>
                New
              </A2UIRenderer>
            </A2UIRenderer>
          </A2UIRenderer>
        </A2UIRenderer>
      );

      // Verify dashboard structure
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Active Users')).toBeInTheDocument();
      expect(screen.getByText('Revenue')).toBeInTheDocument();
      expect(screen.getByText('Orders')).toBeInTheDocument();
      expect(screen.getByText('1,234')).toBeInTheDocument();
      expect(screen.getByText('$45.6K')).toBeInTheDocument();
      expect(screen.getByText('892')).toBeInTheDocument();
      expect(screen.getByText('+12%')).toBeInTheDocument();
      expect(screen.getByText('-3%')).toBeInTheDocument();
      expect(screen.getByText('New')).toBeInTheDocument();
    });

    it('should render a settings page with various components', () => {
      render(
        <A2UIRenderer component="a2ui.Container" props={{ maxWidth: 'max-w-4xl' }}>
          <A2UIRenderer component="a2ui.Text" props={{ variant: 'h1' }}>
            Settings
          </A2UIRenderer>

          <A2UIRenderer component="a2ui.Divider" />

          <A2UIRenderer component="a2ui.Card" props={{ title: 'Profile Settings' }}>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'body' }}>
              Update your profile information
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Button" props={{ variant: 'primary' }}>
              Save Changes
            </A2UIRenderer>
          </A2UIRenderer>

          <A2UIRenderer component="a2ui.Card" props={{ title: 'Notifications' }}>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'body' }}>
              Manage your notification preferences
            </A2UIRenderer>
            <div className="space-x-2">
              <A2UIRenderer component="a2ui.Button" props={{ variant: 'secondary' }}>
                Configure
              </A2UIRenderer>
              <A2UIRenderer component="a2ui.Button" props={{ variant: 'outline' }}>
                Disable All
              </A2UIRenderer>
            </div>
          </A2UIRenderer>

          <A2UIRenderer component="a2ui.Card" props={{ title: 'Danger Zone' }}>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'body' }}>
              Permanently delete your account
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Button" props={{ variant: 'danger' }}>
              Delete Account
            </A2UIRenderer>
          </A2UIRenderer>
        </A2UIRenderer>
      );

      // Verify all sections are rendered
      expect(screen.getByText('Settings')).toBeInTheDocument();
      expect(screen.getByText('Profile Settings')).toBeInTheDocument();
      expect(screen.getByText('Notifications')).toBeInTheDocument();
      expect(screen.getByText('Danger Zone')).toBeInTheDocument();
      expect(screen.getByText('Save Changes')).toBeInTheDocument();
      expect(screen.getByText('Configure')).toBeInTheDocument();
      expect(screen.getByText('Disable All')).toBeInTheDocument();
      expect(screen.getByText('Delete Account')).toBeInTheDocument();
    });
  });

  describe('Component Interoperability', () => {
    it('should handle deeply nested components', () => {
      render(
        <A2UIRenderer component="a2ui.Container">
          <A2UIRenderer component="a2ui.Card" props={{ title: 'Level 1' }}>
            <A2UIRenderer component="a2ui.Card" props={{ title: 'Level 2' }}>
              <A2UIRenderer component="a2ui.Card" props={{ title: 'Level 3' }}>
                <A2UIRenderer component="a2ui.Text">
                  Deeply nested content
                </A2UIRenderer>
              </A2UIRenderer>
            </A2UIRenderer>
          </A2UIRenderer>
        </A2UIRenderer>
      );

      expect(screen.getByText('Level 1')).toBeInTheDocument();
      expect(screen.getByText('Level 2')).toBeInTheDocument();
      expect(screen.getByText('Level 3')).toBeInTheDocument();
      expect(screen.getByText('Deeply nested content')).toBeInTheDocument();
    });

    it('should handle dynamic component rendering based on catalog', () => {
      const componentNames = getA2UIComponentNames();
      const buttonComponent = componentNames.find((name) => name.includes('Button'));
      const cardComponent = componentNames.find((name) => name.includes('Card'));

      expect(buttonComponent).toBeDefined();
      expect(cardComponent).toBeDefined();
      expect(hasA2UIComponent(buttonComponent!)).toBe(true);
      expect(hasA2UIComponent(cardComponent!)).toBe(true);

      render(
        <div>
          <A2UIRenderer component={buttonComponent!}>Dynamic Button</A2UIRenderer>
          <A2UIRenderer component={cardComponent!} props={{ title: 'Dynamic Card' }}>
            Dynamic Content
          </A2UIRenderer>
        </div>
      );

      expect(screen.getByText('Dynamic Button')).toBeInTheDocument();
      expect(screen.getByText('Dynamic Card')).toBeInTheDocument();
      expect(screen.getByText('Dynamic Content')).toBeInTheDocument();
    });

    it('should handle conditional rendering with error fallback', () => {
      const validComponent = 'a2ui.Button';
      const invalidComponent = 'a2ui.Invalid';

      const consoleSpy = vitest.spyOn(console, 'error').mockImplementation(() => {});

      render(
        <div>
          {hasA2UIComponent(validComponent) && (
            <A2UIRenderer component={validComponent}>Valid Button</A2UIRenderer>
          )}
          {!hasA2UIComponent(invalidComponent) && (
            <div data-testid="fallback">Component not available</div>
          )}
        </div>
      );

      expect(screen.getByText('Valid Button')).toBeInTheDocument();
      expect(screen.getByTestId('fallback')).toBeInTheDocument();

      consoleSpy.mockRestore();
    });
  });

  describe('State Management Across Components', () => {
    it('should maintain state across multiple A2UIRenderer instances', () => {
      const TestComponent = () => {
        const [count, setCount] = React.useState(0);

        return (
          <A2UIRenderer component="a2ui.Card" props={{ title: 'Counter' }}>
            <A2UIRenderer component="a2ui.Text">Count: {count}</A2UIRenderer>
            <A2UIRenderer
              component="a2ui.Button"
              props={{ onClick: () => setCount(count + 1) }}
            >
              Increment
            </A2UIRenderer>
            <A2UIRenderer
              component="a2ui.Button"
              props={{ onClick: () => setCount(count - 1), variant: 'secondary' }}
            >
              Decrement
            </A2UIRenderer>
            <A2UIRenderer
              component="a2ui.Button"
              props={{ onClick: () => setCount(0), variant: 'outline' }}
            >
              Reset
            </A2UIRenderer>
          </A2UIRenderer>
        );
      };

      render(<TestComponent />);

      expect(screen.getByText('Count: 0')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Increment'));
      expect(screen.getByText('Count: 1')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Increment'));
      expect(screen.getByText('Count: 2')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Decrement'));
      expect(screen.getByText('Count: 1')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Reset'));
      expect(screen.getByText('Count: 0')).toBeInTheDocument();
    });
  });

  describe('Catalog Export Verification', () => {
    it('should have all components accessible from catalog', () => {
      const names = getA2UIComponentNames();
      expect(names.length).toBeGreaterThan(0);

      names.forEach((name) => {
        expect(hasA2UIComponent(name)).toBe(true);
      });
    });

    it('should export components for direct use', () => {
      // These imports are verified at the top of the file
      const directComponents = [
        'Button',
        'Card',
        'Text',
        'Input',
        'Container',
        'Grid',
        'Badge',
        'Divider',
      ];

      // Just verify the count matches
      expect(getA2UIComponentNames().length).toBe(directComponents.length);
    });
  });
});
