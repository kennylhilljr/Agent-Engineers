/**
 * A2UI Protocol v0.8 Type Definitions
 *
 * Agent-to-UI (A2UI) protocol for LLM-friendly UI component communication.
 * This protocol enables AI agents to emit UI components in a structured,
 * secure, and type-safe manner.
 */

/**
 * Message types supported by A2UI protocol v0.8
 */
export enum A2UIMessageType {
  /** Initial rendering message - starts a new UI surface */
  BEGIN_RENDERING = 'beginRendering',

  /** Update existing surface with new/modified components */
  SURFACE_UPDATE = 'surfaceUpdate',

  /** Update data model without changing component structure */
  DATA_MODEL_UPDATE = 'dataModelUpdate',
}

/**
 * Component types registered in the A2UI catalog
 * These are the ONLY components agents are allowed to emit (security constraint)
 */
export const A2UI_COMPONENT_TYPES = [
  'a2ui.Button',
  'a2ui.Card',
  'a2ui.Text',
  'a2ui.Input',
  'a2ui.Container',
  'a2ui.Grid',
  'a2ui.Badge',
  'a2ui.Divider',
] as const;

export type A2UIComponentType = typeof A2UI_COMPONENT_TYPES[number];

/**
 * Base A2UI Component interface (v0.8 spec)
 *
 * Required fields:
 * - type: Component type from registered catalog
 * - id: Unique identifier for component references
 * - props: Component properties (any valid JSON object)
 */
export interface A2UIComponent {
  /** Component type - MUST be in registered catalog */
  type: A2UIComponentType;

  /** Unique component ID for references and updates */
  id: string;

  /** Component properties (component-specific) */
  props: Record<string, any>;

  /** Optional child component IDs (flat list structure) */
  children?: string[];
}

/**
 * A2UI Message envelope (v0.8 spec)
 *
 * Contains message metadata and flat list of components.
 * Uses ID references for parent-child relationships (LLM-friendly).
 */
export interface A2UIMessage {
  /** Message type */
  messageType: A2UIMessageType;

  /** Flat list of components (no nesting - use ID references) */
  components: A2UIComponent[];

  /** Optional timestamp */
  timestamp?: string;

  /** Optional metadata */
  metadata?: Record<string, any>;
}

/**
 * Validation result for A2UI messages
 */
export interface A2UIValidationResult {
  /** Whether validation passed */
  valid: boolean;

  /** List of validation errors (empty if valid) */
  errors: string[];

  /** List of warnings (non-fatal issues) */
  warnings?: string[];

  /** Validated message (if valid) */
  message?: A2UIMessage;
}

/**
 * Component validation result
 */
export interface A2UIComponentValidationResult {
  /** Whether component is valid */
  valid: boolean;

  /** Validation errors */
  errors: string[];

  /** Component ID (for context) */
  componentId?: string;
}

/**
 * Validation options
 */
export interface A2UIValidationOptions {
  /** Strict mode - treat warnings as errors */
  strict?: boolean;

  /** Allow unknown component types (UNSAFE - for testing only) */
  allowUnknownTypes?: boolean;

  /** Custom component type allowlist (overrides default catalog) */
  customCatalog?: string[];
}

/**
 * Type guard to check if a value is a valid A2UIMessageType
 */
export function isA2UIMessageType(value: any): value is A2UIMessageType {
  return Object.values(A2UIMessageType).includes(value);
}

/**
 * Type guard to check if a value is a valid A2UIComponentType
 */
export function isA2UIComponentType(value: any): value is A2UIComponentType {
  return A2UI_COMPONENT_TYPES.includes(value);
}

/**
 * Type guard to check if a value is a valid A2UIComponent
 */
export function isA2UIComponent(value: any): value is A2UIComponent {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof value.type === 'string' &&
    typeof value.id === 'string' &&
    typeof value.props === 'object' &&
    value.props !== null
  );
}

/**
 * Type guard to check if a value is a valid A2UIMessage
 */
export function isA2UIMessage(value: any): value is A2UIMessage {
  return (
    typeof value === 'object' &&
    value !== null &&
    isA2UIMessageType(value.messageType) &&
    Array.isArray(value.components)
  );
}
