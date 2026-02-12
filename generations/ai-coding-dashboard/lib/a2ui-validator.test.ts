/**
 * Comprehensive test suite for A2UI Protocol Validator (TypeScript)
 *
 * Tests all validation rules, messageType values, catalog compliance,
 * security constraints, and edge cases.
 */

import { describe, it, expect } from 'vitest';
import {
  validateA2UIMessage,
  validateA2UIComponent,
  assertValidA2UIMessage,
  isComponentTypeAllowed,
  getAllowedComponentTypes,
  sanitizeA2UIMessage,
} from './a2ui-validator';
import {
  A2UIMessageType,
  A2UI_COMPONENT_TYPES,
  A2UIMessage,
  A2UIComponent,
} from '@/types/a2ui';

describe('A2UI Message Type Validation', () => {
  it('should validate beginRendering messageType', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Button' as const,
          id: 'btn-1',
          props: { text: 'Click me' },
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('should validate surfaceUpdate messageType', () => {
    const message = {
      messageType: A2UIMessageType.SURFACE_UPDATE,
      components: [
        {
          type: 'a2ui.Text' as const,
          id: 'text-1',
          props: { content: 'Updated' },
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
  });

  it('should validate dataModelUpdate messageType', () => {
    const message = {
      messageType: A2UIMessageType.DATA_MODEL_UPDATE,
      components: [
        {
          type: 'a2ui.Card' as const,
          id: 'card-1',
          props: { title: 'Data' },
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
  });

  it('should reject invalid messageType', () => {
    const message = {
      messageType: 'invalidType',
      components: [],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Invalid messageType'))).toBe(true);
  });

  it('should reject missing messageType', () => {
    const message = {
      components: [],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Missing required field: messageType'))).toBe(true);
  });
});

describe('A2UI Component Validation', () => {
  it('should validate component with all required fields', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Button' as const,
          id: 'btn-1',
          props: {
            variant: 'primary',
            onClick: 'handleClick',
          },
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
  });

  it('should reject component missing type field', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          id: 'btn-1',
          props: {},
        } as any,
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Missing required field "type"'))).toBe(true);
  });

  it('should reject component missing id field', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Button',
          props: {},
        } as any,
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Missing required field "id"'))).toBe(true);
  });

  it('should reject component missing props field', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Button',
          id: 'btn-1',
        } as any,
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Missing required field "props"'))).toBe(true);
  });

  it('should reject component with empty id', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Button' as const,
          id: '',
          props: {},
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('cannot be empty'))).toBe(true);
  });

  it('should reject component with invalid props type', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Button',
          id: 'btn-1',
          props: 'invalid',
        } as any,
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('"props" must be an object'))).toBe(true);
  });
});

describe('Catalog Compliance (Security)', () => {
  it('should accept all registered component types', () => {
    A2UI_COMPONENT_TYPES.forEach((componentType) => {
      const message = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components: [
          {
            type: componentType,
            id: 'test-1',
            props: {},
          },
        ],
      };

      const result = validateA2UIMessage(message);
      expect(result.valid).toBe(true);
    });
  });

  it('should reject unauthorized component type (SECURITY)', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.MaliciousComponent',
          id: 'evil-1',
          props: {},
        } as any,
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Invalid component type'))).toBe(true);
    expect(result.errors.some((e) => e.includes('Not in registered catalog'))).toBe(true);
  });

  it('should accept custom catalog', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Custom',
          id: 'custom-1',
          props: {},
        } as any,
      ],
    };

    const result = validateA2UIMessage(message, {
      customCatalog: ['a2ui.Custom'],
    });
    expect(result.valid).toBe(true);
  });

  it('should allow unknown types with flag (UNSAFE mode)', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Unknown',
          id: 'unknown-1',
          props: {},
        } as any,
      ],
    };

    const result = validateA2UIMessage(message, {
      allowUnknownTypes: true,
    });
    expect(result.valid).toBe(true);
  });
});

describe('Component References', () => {
  it('should validate correct child references', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Container' as const,
          id: 'container-1',
          props: {},
          children: ['btn-1', 'text-1'],
        },
        {
          type: 'a2ui.Button' as const,
          id: 'btn-1',
          props: {},
        },
        {
          type: 'a2ui.Text' as const,
          id: 'text-1',
          props: {},
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
  });

  it('should detect missing child reference', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Container' as const,
          id: 'container-1',
          props: {},
          children: ['btn-1', 'missing-id'],
        },
        {
          type: 'a2ui.Button' as const,
          id: 'btn-1',
          props: {},
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('references non-existent child'))).toBe(true);
  });

  it('should detect duplicate component IDs', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Button' as const,
          id: 'btn-1',
          props: {},
        },
        {
          type: 'a2ui.Text' as const,
          id: 'btn-1',
          props: {},
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Duplicate component ID'))).toBe(true);
  });

  it('should detect circular references', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Container' as const,
          id: 'container-1',
          props: {},
          children: ['container-2'],
        },
        {
          type: 'a2ui.Container' as const,
          id: 'container-2',
          props: {},
          children: ['container-1'],
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Circular reference'))).toBe(true);
  });
});

describe('JSON Structure', () => {
  it('should validate flat list structure (LLM-friendly)', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Container' as const,
          id: 'c1',
          props: {},
          children: ['c2'],
        },
        {
          type: 'a2ui.Container' as const,
          id: 'c2',
          props: {},
          children: ['b1'],
        },
        {
          type: 'a2ui.Button' as const,
          id: 'b1',
          props: {},
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
  });

  it('should reject non-object message', () => {
    const result = validateA2UIMessage([]);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Message must be an object'))).toBe(true);
  });

  it('should reject null message', () => {
    const result = validateA2UIMessage(null);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('Message must be an object'))).toBe(true);
  });
});

describe('Strict Mode', () => {
  it('should fail on warnings in strict mode', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [], // Generates warning
    };

    const result = validateA2UIMessage(message, { strict: true });
    expect(result.valid).toBe(false);
    expect(result.warnings).toBeDefined();
    expect(result.warnings!.length).toBeGreaterThan(0);
  });

  it('should pass on warnings in normal mode', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [],
    };

    const result = validateA2UIMessage(message, { strict: false });
    expect(result.valid).toBe(true);
    expect(result.warnings).toBeDefined();
  });
});

describe('Security Constraints', () => {
  it('should prevent script injection via component type', () => {
    const maliciousTypes = [
      'a2ui.Script',
      'a2ui.Eval',
      "<script>alert('xss')</script>",
      '../../../etc/passwd',
    ];

    maliciousTypes.forEach((maliciousType) => {
      const message = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components: [
          {
            type: maliciousType,
            id: 'test-1',
            props: {},
          } as any,
        ],
      };

      const result = validateA2UIMessage(message);
      expect(result.valid).toBe(false);
    });
  });

  it('should use allowlist approach (more secure)', () => {
    expect(isComponentTypeAllowed('a2ui.Button')).toBe(true);
    expect(isComponentTypeAllowed('a2ui.UnknownComponent')).toBe(false);
    expect(isComponentTypeAllowed('anything.else')).toBe(false);
  });
});

describe('Edge Cases', () => {
  it('should generate warning for empty components array', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
    expect(result.warnings).toBeDefined();
    expect(result.warnings!.some((w) => w.includes('no components'))).toBe(true);
  });

  it('should handle deeply nested references', () => {
    const components = Array.from({ length: 10 }, (_, i) => ({
      type: 'a2ui.Container' as const,
      id: `c${i}`,
      props: {},
      children: [`c${i + 1}`],
    }));

    components.push({
      type: 'a2ui.Button' as const,
      id: 'c10',
      props: {},
    });

    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components,
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
  });

  it('should handle complex nested props', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Card' as const,
          id: 'card-1',
          props: {
            title: 'Test',
            data: {
              nested: {
                deep: {
                  value: [1, 2, 3],
                },
              },
            },
            config: {
              enabled: true,
              count: 42,
            },
          },
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
  });

  it('should handle unicode in props', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Text' as const,
          id: 'text-1',
          props: {
            content: 'Hello 世界 🌍',
          },
        },
      ],
    };

    const result = validateA2UIMessage(message);
    expect(result.valid).toBe(true);
  });
});

describe('Helper Functions', () => {
  it('should check if component type is allowed', () => {
    expect(isComponentTypeAllowed('a2ui.Button')).toBe(true);
    expect(isComponentTypeAllowed('a2ui.Invalid')).toBe(false);
  });

  it('should get all allowed component types', () => {
    const types = getAllowedComponentTypes();
    expect(Array.isArray(types)).toBe(true);
    expect(types).toContain('a2ui.Button');
    expect(types).toHaveLength(A2UI_COMPONENT_TYPES.length);
  });

  it('should throw on invalid message with assertValidA2UIMessage', () => {
    const message = {
      messageType: 'invalid',
      components: [],
    };

    expect(() => assertValidA2UIMessage(message)).toThrow('A2UI validation failed');
  });

  it('should not throw on valid message with assertValidA2UIMessage', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Button' as const,
          id: 'btn-1',
          props: {},
        },
      ],
    };

    expect(() => assertValidA2UIMessage(message)).not.toThrow();
  });
});

describe('Sanitize Function', () => {
  it('should remove invalid components', () => {
    const message = {
      messageType: A2UIMessageType.BEGIN_RENDERING,
      components: [
        {
          type: 'a2ui.Button' as const,
          id: 'btn-1',
          props: {},
        },
        {
          type: 'a2ui.Invalid',
          id: 'invalid-1',
          props: {},
        } as any,
        {
          type: 'a2ui.Text' as const,
          id: 'text-1',
          props: {},
        },
      ],
    };

    const sanitized = sanitizeA2UIMessage(message);
    expect(sanitized.components).toHaveLength(2);
    expect(sanitized.components.map((c) => c.id)).toEqual(['btn-1', 'text-1']);
  });

  it('should handle invalid message gracefully', () => {
    const sanitized = sanitizeA2UIMessage(null);
    expect(sanitized.messageType).toBe(A2UIMessageType.BEGIN_RENDERING);
    expect(sanitized.components).toEqual([]);
  });
});

describe('Component Validation Function', () => {
  it('should validate individual component', () => {
    const component = {
      type: 'a2ui.Button' as const,
      id: 'btn-1',
      props: { text: 'Click' },
    };

    const result = validateA2UIComponent(component, 0);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('should detect errors in individual component', () => {
    const component = {
      type: 'a2ui.Button',
      props: {},
    } as any;

    const result = validateA2UIComponent(component, 0);
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });
});
