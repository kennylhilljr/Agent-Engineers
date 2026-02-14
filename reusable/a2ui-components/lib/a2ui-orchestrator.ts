/**
 * A2UI Orchestrator
 * Dynamic component rendering and orchestration layer for A2UI catalog
 *
 * This module provides a high-level API for working with the A2UI component catalog,
 * enabling dynamic component discovery, validation, and rendering.
 */

import React from 'react';
import {
  a2uiCatalog,
  validateComponentType,
  getComponent,
  getComponentMetadata,
  getAllComponentMetadata,
  getComponentsByCategory,
  renderComponent,
  componentMetadata,
} from '@/lib/a2ui-catalog';
import { A2UIProps, A2UIComponentType, A2UIComponentMetadata } from '@/lib/a2ui-types';

/**
 * Orchestrator response for component requests
 */
export interface OrchestratorResponse {
  success: boolean;
  component?: React.JSX.Element;
  error?: string;
  metadata?: A2UIComponentMetadata;
}

/**
 * Orchestrator configuration
 */
export interface OrchestratorConfig {
  validateProps?: boolean;
  logErrors?: boolean;
  fallbackComponent?: React.ComponentType<any>;
}

/**
 * A2UI Orchestrator class
 * Provides high-level API for component catalog interaction
 */
export class A2UIOrchestratorService {
  private config: OrchestratorConfig;

  constructor(config: OrchestratorConfig = {}) {
    this.config = {
      validateProps: true,
      logErrors: true,
      ...config,
    };
  }

  /**
   * Requests a component to be rendered with given props
   *
   * @param props - A2UI props containing type and data
   * @returns Orchestrator response with component or error
   */
  requestComponent(props: A2UIProps): OrchestratorResponse {
    // Validate component type exists
    if (!validateComponentType(props.type)) {
      const error = `Invalid component type: ${props.type}`;
      if (this.config.logErrors) {
        console.error('[A2UI Orchestrator]', error);
      }
      return {
        success: false,
        error,
      };
    }

    // Get component metadata
    const metadata = getComponentMetadata(props.type);

    // Validate required props if enabled
    if (this.config.validateProps && metadata) {
      const missingProps = this.validateRequiredProps(props, metadata);
      if (missingProps.length > 0) {
        const error = `Missing required props: ${missingProps.join(', ')}`;
        if (this.config.logErrors) {
          console.error('[A2UI Orchestrator]', error);
        }
        return {
          success: false,
          error,
          metadata,
        };
      }
    }

    // Render component
    const component = renderComponent(props);

    if (!component) {
      const error = `Failed to render component: ${props.type}`;
      if (this.config.logErrors) {
        console.error('[A2UI Orchestrator]', error);
      }
      return {
        success: false,
        error,
        metadata,
      };
    }

    return {
      success: true,
      component,
      metadata,
    };
  }

  /**
   * Validates that all required props are present
   *
   * @param props - A2UI props to validate
   * @param metadata - Component metadata
   * @returns Array of missing required props
   */
  private validateRequiredProps(
    props: A2UIProps,
    metadata: A2UIComponentMetadata
  ): string[] {
    const missingProps: string[] = [];

    metadata.propsSchema.required.forEach(prop => {
      if (!(prop in props.data)) {
        missingProps.push(prop);
      }
    });

    return missingProps;
  }

  /**
   * Gets component information without rendering
   *
   * @param type - Component type to query
   * @returns Component metadata if found
   */
  queryComponent(type: string): A2UIComponentMetadata | undefined {
    return getComponentMetadata(type);
  }

  /**
   * Lists all available components
   *
   * @returns Array of all component metadata
   */
  listComponents(): A2UIComponentMetadata[] {
    return getAllComponentMetadata();
  }

  /**
   * Finds components by category
   *
   * @param category - Category to filter by
   * @returns Array of component types in the category
   */
  findByCategory(
    category: 'status' | 'data' | 'interaction' | 'feedback'
  ): A2UIComponentType[] {
    return getComponentsByCategory(category);
  }

  /**
   * Checks if orchestrator is ready
   *
   * @returns true if catalog is valid and ready to use
   */
  isReady(): boolean {
    return Object.keys(a2uiCatalog).length === 9;
  }

  /**
   * Gets orchestrator health status
   *
   * @returns Health status information
   */
  getHealth(): {
    ready: boolean;
    componentCount: number;
    categories: Record<string, number>;
    version: string;
  } {
    const categories = {
      status: this.findByCategory('status').length,
      data: this.findByCategory('data').length,
      interaction: this.findByCategory('interaction').length,
      feedback: this.findByCategory('feedback').length,
    };

    return {
      ready: this.isReady(),
      componentCount: getAllComponentMetadata().length,
      categories,
      version: '1.0.0',
    };
  }
}

/**
 * Global orchestrator instance
 */
export const orchestrator = new A2UIOrchestratorService({
  validateProps: true,
  logErrors: true,
});

/**
 * Convenience function to render a component via orchestrator
 *
 * @param props - A2UI props
 * @returns React element or null on error
 */
export function renderA2UIComponent(props: A2UIProps): React.JSX.Element | null {
  const response = orchestrator.requestComponent(props);
  return response.success ? response.component || null : null;
}

/**
 * Convenience function to get component metadata
 *
 * @param type - Component type
 * @returns Component metadata or undefined
 */
export function getA2UIComponentInfo(type: string): A2UIComponentMetadata | undefined {
  return orchestrator.queryComponent(type);
}

/**
 * Convenience function to check if component type is valid
 *
 * @param type - Component type to validate
 * @returns true if component exists in catalog
 */
export function isValidA2UIComponent(type: string): boolean {
  return validateComponentType(type);
}
