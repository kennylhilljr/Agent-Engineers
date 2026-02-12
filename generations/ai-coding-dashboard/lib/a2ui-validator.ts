/**
 * A2UI Protocol Validator (Client-side TypeScript)
 *
 * Validates A2UI messages against v0.8 specification before rendering.
 * Ensures type safety and security constraints.
 */

import {
  A2UIMessage,
  A2UIComponent,
  A2UIMessageType,
  A2UIComponentType,
  A2UI_COMPONENT_TYPES,
  A2UIValidationResult,
  A2UIComponentValidationResult,
  A2UIValidationOptions,
  isA2UIMessageType,
  isA2UIComponentType,
} from '@/types/a2ui';

/**
 * Validate an A2UI message against v0.8 specification
 *
 * @param message - The A2UI message to validate
 * @param options - Validation options
 * @returns Validation result with errors/warnings
 */
export function validateA2UIMessage(
  message: any,
  options: A2UIValidationOptions = {}
): A2UIValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Check if message is an object (not an array or null)
  if (typeof message !== 'object' || message === null || Array.isArray(message)) {
    return {
      valid: false,
      errors: ['Message must be an object'],
    };
  }

  // Validate messageType
  if (!message.messageType) {
    errors.push('Missing required field: messageType');
  } else if (!isA2UIMessageType(message.messageType)) {
    errors.push(
      `Invalid messageType: "${message.messageType}". Must be one of: ${Object.values(A2UIMessageType).join(', ')}`
    );
  }

  // Validate components array
  if (!message.components) {
    errors.push('Missing required field: components');
  } else if (!Array.isArray(message.components)) {
    errors.push('Field "components" must be an array');
  } else {
    // Validate each component
    const componentIds = new Set<string>();

    message.components.forEach((component: any, index: number) => {
      const componentResult = validateA2UIComponent(component, index, options);

      if (!componentResult.valid) {
        errors.push(...componentResult.errors);
      }

      // Check for duplicate IDs
      if (component.id) {
        if (componentIds.has(component.id)) {
          errors.push(`Duplicate component ID: "${component.id}"`);
        }
        componentIds.add(component.id);
      }
    });

    // Validate child references
    message.components.forEach((component: any) => {
      if (component.children && Array.isArray(component.children)) {
        component.children.forEach((childId: string) => {
          if (!componentIds.has(childId)) {
            errors.push(
              `Component "${component.id}" references non-existent child: "${childId}"`
            );
          }
        });
      }
    });
  }

  // Check for circular references (children cannot reference ancestors)
  if (message.components && Array.isArray(message.components)) {
    const circularRefErrors = detectCircularReferences(message.components);
    errors.push(...circularRefErrors);
  }

  // Warnings
  if (message.components && message.components.length === 0) {
    warnings.push('Message contains no components');
  }

  const valid = errors.length === 0 && (!options.strict || warnings.length === 0);

  return {
    valid,
    errors,
    warnings: warnings.length > 0 ? warnings : undefined,
    message: valid ? (message as A2UIMessage) : undefined,
  };
}

/**
 * Validate a single A2UI component
 *
 * @param component - The component to validate
 * @param index - Component index (for error messages)
 * @param options - Validation options
 * @returns Component validation result
 */
export function validateA2UIComponent(
  component: any,
  index: number,
  options: A2UIValidationOptions = {}
): A2UIComponentValidationResult {
  const errors: string[] = [];
  const prefix = `Component[${index}]`;

  // Check if component is an object
  if (typeof component !== 'object' || component === null) {
    return {
      valid: false,
      errors: [`${prefix}: Must be an object`],
    };
  }

  // Validate required fields
  if (!component.type) {
    errors.push(`${prefix}: Missing required field "type"`);
  } else if (typeof component.type !== 'string') {
    errors.push(`${prefix}: Field "type" must be a string`);
  } else {
    // Validate component type is in catalog
    const catalog = options.customCatalog || A2UI_COMPONENT_TYPES;

    if (!options.allowUnknownTypes && !catalog.includes(component.type)) {
      errors.push(
        `${prefix}: Invalid component type "${component.type}". Not in registered catalog. Allowed types: ${catalog.join(', ')}`
      );
    }
  }

  if (component.id === undefined || component.id === null) {
    errors.push(`${prefix}: Missing required field "id"`);
  } else if (typeof component.id !== 'string') {
    errors.push(`${prefix}: Field "id" must be a string`);
  } else if (component.id.trim() === '') {
    errors.push(`${prefix}: Field "id" cannot be empty`);
  }

  if (component.props === undefined) {
    errors.push(`${prefix}: Missing required field "props"`);
  } else if (typeof component.props !== 'object' || component.props === null) {
    errors.push(`${prefix}: Field "props" must be an object`);
  }

  // Validate children (optional)
  if (component.children !== undefined) {
    if (!Array.isArray(component.children)) {
      errors.push(`${prefix}: Field "children" must be an array of strings`);
    } else {
      component.children.forEach((child: any, childIndex: number) => {
        if (typeof child !== 'string') {
          errors.push(
            `${prefix}: children[${childIndex}] must be a string (component ID)`
          );
        }
      });
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    componentId: component.id,
  };
}

/**
 * Detect circular references in component tree
 *
 * @param components - List of components to check
 * @returns List of error messages for circular references
 */
function detectCircularReferences(components: A2UIComponent[]): string[] {
  const errors: string[] = [];
  const componentMap = new Map<string, A2UIComponent>();

  // Build component map
  components.forEach((c) => componentMap.set(c.id, c));

  // Check each component for circular references
  components.forEach((component) => {
    if (!component.children) return;

    const visited = new Set<string>();
    const stack = [component.id];

    while (stack.length > 0) {
      const currentId = stack.pop()!;

      if (visited.has(currentId)) {
        errors.push(`Circular reference detected involving component "${currentId}"`);
        break;
      }

      visited.add(currentId);
      const current = componentMap.get(currentId);

      if (current?.children) {
        current.children.forEach((childId) => {
          if (childId === component.id) {
            errors.push(
              `Circular reference: Component "${component.id}" references itself through child "${currentId}"`
            );
          } else {
            stack.push(childId);
          }
        });
      }
    }
  });

  return errors;
}

/**
 * Validate A2UI message and throw if invalid
 *
 * @param message - Message to validate
 * @param options - Validation options
 * @throws Error if validation fails
 */
export function assertValidA2UIMessage(
  message: any,
  options: A2UIValidationOptions = {}
): asserts message is A2UIMessage {
  const result = validateA2UIMessage(message, options);

  if (!result.valid) {
    throw new Error(
      `A2UI validation failed:\n${result.errors.join('\n')}`
    );
  }
}

/**
 * Check if a component type is in the registered catalog
 *
 * @param componentType - Component type to check
 * @param customCatalog - Optional custom catalog (defaults to built-in catalog)
 * @returns true if component type is allowed
 */
export function isComponentTypeAllowed(
  componentType: string,
  customCatalog?: string[]
): boolean {
  const catalog = customCatalog || A2UI_COMPONENT_TYPES;
  return catalog.includes(componentType);
}

/**
 * Get list of all registered component types
 *
 * @param customCatalog - Optional custom catalog
 * @returns Array of allowed component type names
 */
export function getAllowedComponentTypes(customCatalog?: string[]): string[] {
  return customCatalog || [...A2UI_COMPONENT_TYPES];
}

/**
 * Sanitize an A2UI message by removing invalid components
 *
 * @param message - Message to sanitize
 * @param options - Validation options
 * @returns Sanitized message with only valid components
 */
export function sanitizeA2UIMessage(
  message: any,
  options: A2UIValidationOptions = {}
): A2UIMessage {
  if (!message || typeof message !== 'object') {
    return {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [],
    };
  }

  const messageType = isA2UIMessageType(message.messageType)
    ? message.messageType
    : A2UIMessageType.BEGIN_RENDERING;

  const validComponents: A2UIComponent[] = [];

  if (Array.isArray(message.components)) {
    message.components.forEach((component: any, index: number) => {
      const result = validateA2UIComponent(component, index, options);
      if (result.valid) {
        validComponents.push(component);
      }
    });
  }

  return {
    messageType,
    components: validComponents,
    timestamp: message.timestamp,
    metadata: message.metadata,
  };
}
