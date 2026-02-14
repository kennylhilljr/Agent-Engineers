/**
 * A2UI Component Catalog
 * Central registry for all approved A2UI components
 *
 * This catalog maps component type strings to their React component implementations.
 * Only components registered in this catalog can be used by the generative UI system.
 */

import React from 'react';
import { TaskCard } from '@/components/a2ui-catalog/task-card';
import { ProgressRing } from '@/components/a2ui-catalog/progress-ring';
import { FileTree as FileTreeBase } from '@/components/a2ui-catalog/file-tree';
import { TestResults } from '@/components/a2ui-catalog/test-results';
import { ActivityItem as ActivityItemBase } from '@/components/a2ui-catalog/activity-item';
import { ApprovalCard } from '@/components/a2ui-catalog/approval-card';
import { DecisionCard } from '@/components/a2ui-catalog/decision-card';
import { MilestoneCard } from '@/components/a2ui-catalog/milestone-card';
import { ErrorCard } from '@/components/a2ui-catalog/error-card';

import {
  A2UICatalog,
  A2UIComponent,
  A2UIComponentType,
  A2UIProps,
} from '@/lib/a2ui-types';

/**
 * ActivityItem Wrapper Component
 * Unwraps A2UIProps and passes data to the base ActivityItem component
 */
function ActivityItem({ type, data, metadata, onEvent }: A2UIProps): React.JSX.Element {
  // The ActivityItem expects direct props, so we unwrap data and pass it
  // Ensure timestamp is a Date object if it's a string
  const activityProps = {
    ...data,
    timestamp: data.timestamp instanceof Date ? data.timestamp : new Date(data.timestamp as string),
  } as any;
  return React.createElement(ActivityItemBase, activityProps);
}

/**
 * FileTree Wrapper Component
 * Unwraps A2UIProps and passes data and onEvent to the base FileTree component
 */
function FileTree({ type, data, metadata, onEvent }: A2UIProps): React.JSX.Element {
  // FileTree expects { data, onEvent }
  return React.createElement(FileTreeBase, { data, onEvent } as any);
}

/**
 * The A2UI Component Catalog
 * Maps component type strings to React components
 */
export const a2uiCatalog: A2UICatalog = {
  'a2ui.TaskCard': TaskCard,
  'a2ui.ProgressRing': ProgressRing,
  'a2ui.FileTree': FileTree,
  'a2ui.TestResults': TestResults,
  'a2ui.ActivityItem': ActivityItem,
  'a2ui.ApprovalCard': ApprovalCard,
  'a2ui.DecisionCard': DecisionCard,
  'a2ui.MilestoneCard': MilestoneCard,
  'a2ui.ErrorCard': ErrorCard,
};

/**
 * List of all registered component types
 */
export const registeredComponentTypes: A2UIComponentType[] = [
  'a2ui.TaskCard',
  'a2ui.ProgressRing',
  'a2ui.FileTree',
  'a2ui.TestResults',
  'a2ui.ActivityItem',
  'a2ui.ApprovalCard',
  'a2ui.DecisionCard',
  'a2ui.MilestoneCard',
  'a2ui.ErrorCard',
];

/**
 * Validates if a component type is registered in the catalog
 * Uses hasOwnProperty to prevent prototype pollution attacks
 *
 * @param type - The component type string to validate
 * @returns true if the component type exists in the catalog
 *
 * @example
 * validateComponentType('a2ui.TaskCard') // true
 * validateComponentType('a2ui.Unknown') // false
 */
export function validateComponentType(type: string): type is A2UIComponentType {
  return Object.prototype.hasOwnProperty.call(a2uiCatalog, type);
}

/**
 * Gets a component from the catalog by type
 *
 * @param type - The component type string
 * @returns The React component if found, undefined otherwise
 *
 * @example
 * const Component = getComponent('a2ui.TaskCard');
 * if (Component) {
 *   return <Component type="a2ui.TaskCard" data={data} />;
 * }
 */
export function getComponent(type: string): A2UIComponent | undefined {
  if (!validateComponentType(type)) {
    return undefined;
  }
  return a2uiCatalog[type];
}

/**
 * Safely extracts a property from component data
 *
 * @param props - The A2UI props object
 * @param key - The property key to extract
 * @param defaultValue - Default value if property is not found
 * @returns The property value or default value
 *
 * @example
 * const title = getComponentProp(props, 'title', 'Untitled');
 */
export function getComponentProp<T = any>(
  props: A2UIProps,
  key: string,
  defaultValue?: T
): T {
  if (props.data && key in props.data) {
    return props.data[key] as T;
  }
  return defaultValue as T;
}

/**
 * Gets all registered component types
 *
 * @returns Array of all registered component type strings
 */
export function getAllComponentTypes(): A2UIComponentType[] {
  return [...registeredComponentTypes];
}

/**
 * Gets the total count of registered components
 *
 * @returns Number of components in the catalog
 */
export function getComponentCount(): number {
  return registeredComponentTypes.length;
}

/**
 * Checks if the catalog is properly initialized
 * Validates that all expected components are registered
 *
 * @returns true if catalog has all 9 expected components
 */
export function isCatalogValid(): boolean {
  return getComponentCount() === 9 &&
         registeredComponentTypes.every(type => validateComponentType(type));
}
