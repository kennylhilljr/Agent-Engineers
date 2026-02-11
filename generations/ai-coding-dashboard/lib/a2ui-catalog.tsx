import React from 'react';

/**
 * A2UI Component Catalog
 * Maps a2ui.* component names to actual React components
 */

// Base component types
export type A2UIComponentProps = Record<string, any>;
export type A2UIComponent = React.ComponentType<A2UIComponentProps>;

// Catalog type definition
export type A2UICatalog = Record<string, A2UIComponent>;

// Basic UI Components
const Button: React.FC<A2UIComponentProps> = ({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  className = '',
  ...props
}) => {
  const baseClasses = 'px-4 py-2 rounded-lg font-semibold transition-all duration-200';
  const variantClasses = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white disabled:bg-blue-400',
    secondary: 'bg-gray-600 hover:bg-gray-700 text-white disabled:bg-gray-400',
    outline: 'border-2 border-blue-600 text-blue-600 hover:bg-blue-50 disabled:border-blue-400',
    danger: 'bg-red-600 hover:bg-red-700 text-white disabled:bg-red-400',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${baseClasses} ${variantClasses[variant as keyof typeof variantClasses] || variantClasses.primary} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
};

const Card: React.FC<A2UIComponentProps> = ({
  children,
  title,
  className = '',
  ...props
}) => {
  return (
    <div className={`p-6 border border-gray-700 rounded-lg bg-gray-800 ${className}`} {...props}>
      {title && <h3 className="text-xl font-semibold mb-4 text-white">{title}</h3>}
      <div className="text-gray-300">{children}</div>
    </div>
  );
};

const Text: React.FC<A2UIComponentProps> = ({
  children,
  variant = 'body',
  className = '',
  ...props
}) => {
  const variantClasses = {
    h1: 'text-4xl font-bold',
    h2: 'text-3xl font-semibold',
    h3: 'text-2xl font-semibold',
    h4: 'text-xl font-semibold',
    body: 'text-base',
    small: 'text-sm',
    caption: 'text-xs text-gray-400',
  };

  const Component = ['h1', 'h2', 'h3', 'h4'].includes(variant) ? variant : 'p';

  return React.createElement(
    Component,
    {
      className: `${variantClasses[variant as keyof typeof variantClasses] || variantClasses.body} ${className}`,
      ...props,
    },
    children
  );
};

const Input: React.FC<A2UIComponentProps> = ({
  type = 'text',
  placeholder,
  value,
  onChange,
  className = '',
  ...props
}) => {
  return (
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      className={`px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 ${className}`}
      {...props}
    />
  );
};

const Container: React.FC<A2UIComponentProps> = ({
  children,
  className = '',
  maxWidth = 'max-w-7xl',
  ...props
}) => {
  return (
    <div className={`${maxWidth} mx-auto px-4 sm:px-6 lg:px-8 ${className}`} {...props}>
      {children}
    </div>
  );
};

const GRID_COLS: Record<string, string> = {
  '1': 'grid-cols-1',
  '2': 'grid-cols-2',
  '3': 'grid-cols-3',
  '4': 'grid-cols-4',
  '5': 'grid-cols-5',
  '6': 'grid-cols-6',
};

const GRID_GAPS: Record<string, string> = {
  '0': 'gap-0',
  '1': 'gap-1',
  '2': 'gap-2',
  '3': 'gap-3',
  '4': 'gap-4',
  '5': 'gap-5',
  '6': 'gap-6',
  '8': 'gap-8',
};

const Grid: React.FC<A2UIComponentProps> = ({
  children,
  cols = '1',
  gap = '4',
  className = '',
  ...props
}) => {
  const colsClass = GRID_COLS[cols] || 'grid-cols-1';
  const gapClass = GRID_GAPS[gap] || 'gap-4';

  return (
    <div className={`grid ${colsClass} ${gapClass} ${className}`} {...props}>
      {children}
    </div>
  );
};

const Badge: React.FC<A2UIComponentProps> = ({
  children,
  variant = 'default',
  className = '',
  ...props
}) => {
  const variantClasses = {
    default: 'bg-gray-600 text-white',
    success: 'bg-green-600 text-white',
    warning: 'bg-yellow-600 text-white',
    error: 'bg-red-600 text-white',
    info: 'bg-blue-600 text-white',
  };

  return (
    <span
      className={`inline-block px-3 py-1 text-xs font-semibold rounded-full ${variantClasses[variant as keyof typeof variantClasses] || variantClasses.default} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
};

const Divider: React.FC<A2UIComponentProps> = ({
  className = '',
  ...props
}) => {
  return <hr className={`border-gray-700 my-4 ${className}`} {...props} />;
};

// A2UI Component Catalog
export const a2uiCatalog: A2UICatalog = {
  'a2ui.Button': Button,
  'a2ui.Card': Card,
  'a2ui.Text': Text,
  'a2ui.Input': Input,
  'a2ui.Container': Container,
  'a2ui.Grid': Grid,
  'a2ui.Badge': Badge,
  'a2ui.Divider': Divider,
};

// A2UIRenderer Props
export interface A2UIRendererProps {
  component: string;
  props?: A2UIComponentProps;
  children?: React.ReactNode;
}

/**
 * A2UIRenderer Component
 * Renders components from the A2UI catalog by name
 */
export const A2UIRenderer: React.FC<A2UIRendererProps> = ({
  component,
  props = {},
  children
}) => {
  const Component = a2uiCatalog[component];

  if (!Component) {
    console.error(`A2UI component "${component}" not found in catalog`);
    return (
      <div className="p-4 bg-red-900 border border-red-700 rounded-lg text-red-200">
        <strong>Error:</strong> Component "{component}" not found in A2UI catalog
      </div>
    );
  }

  return <Component {...props}>{children}</Component>;
};

/**
 * Helper function to check if a component exists in the catalog
 */
export const hasA2UIComponent = (componentName: string): boolean => {
  return componentName in a2uiCatalog;
};

/**
 * Helper function to get all available component names
 */
export const getA2UIComponentNames = (): string[] => {
  return Object.keys(a2uiCatalog);
};

// Export individual components for direct use if needed
export { Button, Card, Text, Input, Container, Grid, Badge, Divider };
