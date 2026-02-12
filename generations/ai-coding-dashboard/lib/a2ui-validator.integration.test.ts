/**
 * Integration tests for A2UI Protocol Validator
 *
 * Tests end-to-end validation workflows including:
 * - Valid A2UI messages
 * - Invalid messages with various error types
 * - Security constraints
 * - Edge cases
 */

import { describe, it, expect } from 'vitest';
import {
  validateA2UIMessage,
  sanitizeA2UIMessage,
  assertValidA2UIMessage,
} from './a2ui-validator';
import { A2UIMessageType } from '@/types/a2ui';

describe('A2UI Validator Integration Tests', () => {
  describe('Real-world Valid Messages', () => {
    it('should validate dashboard UI message', () => {
      const dashboardMessage = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components: [
          {
            type: 'a2ui.Container' as const,
            id: 'dashboard-root',
            props: { maxWidth: 'max-w-7xl' },
            children: ['header-1', 'stats-grid', 'action-panel'],
          },
          {
            type: 'a2ui.Card' as const,
            id: 'header-1',
            props: { title: 'Project Dashboard' },
            children: ['title-text'],
          },
          {
            type: 'a2ui.Text' as const,
            id: 'title-text',
            props: { variant: 'h1', content: 'Welcome to Your Dashboard' },
          },
          {
            type: 'a2ui.Grid' as const,
            id: 'stats-grid',
            props: { cols: '3', gap: '6' },
            children: ['stat-1', 'stat-2', 'stat-3'],
          },
          {
            type: 'a2ui.Card' as const,
            id: 'stat-1',
            props: { title: 'Tasks Completed' },
            children: ['stat-1-badge'],
          },
          {
            type: 'a2ui.Badge' as const,
            id: 'stat-1-badge',
            props: { variant: 'success', children: '42' },
          },
          {
            type: 'a2ui.Card' as const,
            id: 'stat-2',
            props: { title: 'In Progress' },
            children: ['stat-2-badge'],
          },
          {
            type: 'a2ui.Badge' as const,
            id: 'stat-2-badge',
            props: { variant: 'info', children: '12' },
          },
          {
            type: 'a2ui.Card' as const,
            id: 'stat-3',
            props: { title: 'Pending' },
            children: ['stat-3-badge'],
          },
          {
            type: 'a2ui.Badge' as const,
            id: 'stat-3-badge',
            props: { variant: 'warning', children: '5' },
          },
          {
            type: 'a2ui.Container' as const,
            id: 'action-panel',
            props: {},
            children: ['action-btn'],
          },
          {
            type: 'a2ui.Button' as const,
            id: 'action-btn',
            props: { variant: 'primary', text: 'Create New Task' },
          },
        ],
        timestamp: new Date().toISOString(),
        metadata: {
          source: 'agent',
          version: '1.0',
        },
      };

      const result = validateA2UIMessage(dashboardMessage);
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
      expect(result.message).toBeDefined();
    });

    it('should validate form UI message', () => {
      const formMessage = {
        messageType: A2UIMessageType.SURFACE_UPDATE,
        components: [
          {
            type: 'a2ui.Card' as const,
            id: 'form-card',
            props: { title: 'User Profile' },
            children: ['name-input', 'email-input', 'divider-1', 'submit-btn'],
          },
          {
            type: 'a2ui.Input' as const,
            id: 'name-input',
            props: { type: 'text', placeholder: 'Enter your name' },
          },
          {
            type: 'a2ui.Input' as const,
            id: 'email-input',
            props: { type: 'email', placeholder: 'Enter your email' },
          },
          {
            type: 'a2ui.Divider' as const,
            id: 'divider-1',
            props: {},
          },
          {
            type: 'a2ui.Button' as const,
            id: 'submit-btn',
            props: { variant: 'primary', text: 'Save Profile' },
          },
        ],
      };

      const result = validateA2UIMessage(formMessage);
      expect(result.valid).toBe(true);
    });
  });

  describe('Real-world Invalid Messages', () => {
    it('should catch missing component IDs', () => {
      const invalidMessage = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components: [
          {
            type: 'a2ui.Button' as const,
            props: { text: 'Button without ID' },
          } as any,
        ],
      };

      const result = validateA2UIMessage(invalidMessage);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.includes('Missing required field "id"'))).toBe(
        true
      );
    });

    it('should catch orphaned child references', () => {
      const invalidMessage = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components: [
          {
            type: 'a2ui.Container' as const,
            id: 'container-1',
            props: {},
            children: ['button-1', 'button-2', 'missing-child'],
          },
          {
            type: 'a2ui.Button' as const,
            id: 'button-1',
            props: {},
          },
          {
            type: 'a2ui.Button' as const,
            id: 'button-2',
            props: {},
          },
        ],
      };

      const result = validateA2UIMessage(invalidMessage);
      expect(result.valid).toBe(false);
      expect(
        result.errors.some((e) => e.includes('references non-existent child'))
      ).toBe(true);
    });

    it('should detect complex circular references', () => {
      const circularMessage = {
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
            children: ['c3'],
          },
          {
            type: 'a2ui.Container' as const,
            id: 'c3',
            props: {},
            children: ['c1'], // Circular!
          },
        ],
      };

      const result = validateA2UIMessage(circularMessage);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.includes('Circular reference'))).toBe(true);
    });
  });

  describe('Security Validation', () => {
    it('should block XSS attempt via component type', () => {
      const xssAttempt = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components: [
          {
            type: '<script>alert("XSS")</script>',
            id: 'evil-1',
            props: {},
          } as any,
        ],
      };

      const result = validateA2UIMessage(xssAttempt);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.includes('Invalid component type'))).toBe(
        true
      );
    });

    it('should block path traversal via component type', () => {
      const pathTraversal = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components: [
          {
            type: '../../../etc/passwd',
            id: 'hack-1',
            props: {},
          } as any,
        ],
      };

      const result = validateA2UIMessage(pathTraversal);
      expect(result.valid).toBe(false);
    });

    it('should block unauthorized component injection', () => {
      const unauthorizedComponents = [
        'a2ui.Exec',
        'a2ui.System',
        'a2ui.FileUpload',
        'a2ui.DatabaseQuery',
        'CustomComponent',
      ];

      unauthorizedComponents.forEach((componentType) => {
        const message = {
          messageType: A2UIMessageType.BEGIN_RENDERING,
          components: [
            {
              type: componentType,
              id: 'test-1',
              props: {},
            } as any,
          ],
        };

        const result = validateA2UIMessage(message);
        expect(result.valid).toBe(false);
        expect(
          result.errors.some((e) => e.includes('Not in registered catalog'))
        ).toBe(true);
      });
    });
  });

  describe('Message Type Validation', () => {
    it('should validate all three message types', () => {
      const messageTypes = [
        A2UIMessageType.BEGIN_RENDERING,
        A2UIMessageType.SURFACE_UPDATE,
        A2UIMessageType.DATA_MODEL_UPDATE,
      ];

      messageTypes.forEach((messageType) => {
        const message = {
          messageType,
          components: [
            {
              type: 'a2ui.Button' as const,
              id: 'btn-1',
              props: {},
            },
          ],
        };

        const result = validateA2UIMessage(message);
        expect(result.valid).toBe(true);
      });
    });

    it('should reject typos in message type', () => {
      const typos = [
        'beginrendering', // lowercase
        'BeginRendering', // capitalized
        'begin_rendering', // snake_case
        'surfacUpdate', // missing 'e'
        'dataModelUpate', // missing 'd'
      ];

      typos.forEach((typo) => {
        const message = {
          messageType: typo,
          components: [],
        };

        const result = validateA2UIMessage(message);
        expect(result.valid).toBe(false);
      });
    });
  });

  describe('Sanitization', () => {
    it('should sanitize message by removing invalid components', () => {
      const mixedMessage = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components: [
          {
            type: 'a2ui.Button' as const,
            id: 'valid-1',
            props: { text: 'Valid' },
          },
          {
            type: 'a2ui.Malicious',
            id: 'invalid-1',
            props: {},
          } as any,
          {
            type: 'a2ui.Text' as const,
            id: 'valid-2',
            props: { content: 'Also valid' },
          },
          {
            id: 'missing-type',
            props: {},
          } as any,
        ],
      };

      const sanitized = sanitizeA2UIMessage(mixedMessage);
      expect(sanitized.components).toHaveLength(2);
      expect(sanitized.components.map((c) => c.id)).toEqual(['valid-1', 'valid-2']);
    });

    it('should handle completely invalid message gracefully', () => {
      const sanitized = sanitizeA2UIMessage({ invalid: 'structure' });
      expect(sanitized.messageType).toBe(A2UIMessageType.BEGIN_RENDERING);
      expect(sanitized.components).toEqual([]);
    });
  });

  describe('Assert Function', () => {
    it('should not throw for valid message', () => {
      const validMessage = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components: [
          {
            type: 'a2ui.Button' as const,
            id: 'btn-1',
            props: {},
          },
        ],
      };

      expect(() => assertValidA2UIMessage(validMessage)).not.toThrow();
    });

    it('should throw with detailed error for invalid message', () => {
      const invalidMessage = {
        messageType: 'invalid',
        components: [
          {
            type: 'a2ui.Invalid',
            id: 'test-1',
            props: {},
          } as any,
        ],
      };

      expect(() => assertValidA2UIMessage(invalidMessage)).toThrow(
        /A2UI validation failed/
      );
    });
  });

  describe('Performance and Scalability', () => {
    it('should handle large messages efficiently', () => {
      const components = Array.from({ length: 100 }, (_, i) => ({
        type: 'a2ui.Card' as const,
        id: `card-${i}`,
        props: { title: `Card ${i}` },
      }));

      const largeMessage = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components,
      };

      const start = Date.now();
      const result = validateA2UIMessage(largeMessage);
      const duration = Date.now() - start;

      expect(result.valid).toBe(true);
      expect(duration).toBeLessThan(100); // Should complete in under 100ms
    });

    it('should handle deeply nested component references', () => {
      const components = Array.from({ length: 50 }, (_, i) => ({
        type: 'a2ui.Container' as const,
        id: `c${i}`,
        props: {},
        children: i < 49 ? [`c${i + 1}`] : undefined,
      }));

      const deepMessage = {
        messageType: A2UIMessageType.BEGIN_RENDERING,
        components,
      };

      const result = validateA2UIMessage(deepMessage);
      expect(result.valid).toBe(true);
    });
  });
});
