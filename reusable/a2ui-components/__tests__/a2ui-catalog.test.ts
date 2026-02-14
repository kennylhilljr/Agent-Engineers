/**
 * A2UI Catalog Unit Tests
 * Comprehensive test suite for the A2UI component catalog system
 */

import {
  a2uiCatalog,
  registeredComponentTypes,
  validateComponentType,
  getComponent,
  getComponentProp,
  getAllComponentTypes,
  getComponentCount,
  isCatalogValid,
} from '@/lib/a2ui-catalog';

import {
  A2UIComponentType,
  A2UIProps,
  A2UIEventType,
  A2UIMessageType,
} from '@/lib/a2ui-types';

describe('A2UI Catalog - Core Functionality', () => {
  describe('Catalog Structure', () => {
    test('catalog object exists and is defined', () => {
      expect(a2uiCatalog).toBeDefined();
      expect(typeof a2uiCatalog).toBe('object');
    });

    test('catalog contains exactly 9 components', () => {
      const componentCount = Object.keys(a2uiCatalog).length;
      expect(componentCount).toBe(9);
    });

    test('registeredComponentTypes array contains 9 types', () => {
      expect(registeredComponentTypes).toBeDefined();
      expect(registeredComponentTypes.length).toBe(9);
    });

    test('all expected component types are registered', () => {
      const expectedTypes: A2UIComponentType[] = [
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

      expectedTypes.forEach(type => {
        expect(registeredComponentTypes).toContain(type);
      });
    });

    test('catalog keys match registeredComponentTypes', () => {
      const catalogKeys = Object.keys(a2uiCatalog);

      registeredComponentTypes.forEach(type => {
        expect(catalogKeys).toContain(type);
      });
    });

    test('all catalog entries are functions (React components)', () => {
      Object.values(a2uiCatalog).forEach(component => {
        expect(typeof component).toBe('function');
      });
    });
  });

  describe('validateComponentType()', () => {
    test('returns true for valid component types', () => {
      expect(validateComponentType('a2ui.TaskCard')).toBe(true);
      expect(validateComponentType('a2ui.ProgressRing')).toBe(true);
      expect(validateComponentType('a2ui.FileTree')).toBe(true);
      expect(validateComponentType('a2ui.TestResults')).toBe(true);
      expect(validateComponentType('a2ui.ActivityItem')).toBe(true);
      expect(validateComponentType('a2ui.ApprovalCard')).toBe(true);
      expect(validateComponentType('a2ui.DecisionCard')).toBe(true);
      expect(validateComponentType('a2ui.MilestoneCard')).toBe(true);
      expect(validateComponentType('a2ui.ErrorCard')).toBe(true);
    });

    test('returns false for invalid component types', () => {
      expect(validateComponentType('a2ui.Unknown')).toBe(false);
      expect(validateComponentType('InvalidComponent')).toBe(false);
      expect(validateComponentType('')).toBe(false);
      expect(validateComponentType('a2ui.')).toBe(false);
    });

    test('returns false for malicious input', () => {
      expect(validateComponentType('__proto__')).toBe(false);
      expect(validateComponentType('constructor')).toBe(false);
      expect(validateComponentType('prototype')).toBe(false);
    });

    test('is case-sensitive', () => {
      expect(validateComponentType('a2ui.taskcard')).toBe(false);
      expect(validateComponentType('A2UI.TaskCard')).toBe(false);
      expect(validateComponentType('a2ui.TASKCARD')).toBe(false);
    });
  });

  describe('getComponent()', () => {
    test('returns component for valid types', () => {
      const component = getComponent('a2ui.TaskCard');
      expect(component).toBeDefined();
      expect(typeof component).toBe('function');
    });

    test('returns undefined for invalid types', () => {
      expect(getComponent('a2ui.Unknown')).toBeUndefined();
      expect(getComponent('InvalidComponent')).toBeUndefined();
      expect(getComponent('')).toBeUndefined();
    });

    test('returns correct component for each type', () => {
      registeredComponentTypes.forEach(type => {
        const component = getComponent(type);
        expect(component).toBe(a2uiCatalog[type]);
      });
    });

    test('returns undefined for malicious input', () => {
      expect(getComponent('__proto__')).toBeUndefined();
      expect(getComponent('constructor')).toBeUndefined();
      expect(getComponent('prototype')).toBeUndefined();
    });
  });

  describe('getComponentProp()', () => {
    test('extracts existing property from data', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Test Task', status: 'pending' },
      };

      expect(getComponentProp(props, 'title')).toBe('Test Task');
      expect(getComponentProp(props, 'status')).toBe('pending');
    });

    test('returns default value for missing property', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Test Task' },
      };

      expect(getComponentProp(props, 'status', 'default')).toBe('default');
      expect(getComponentProp(props, 'missing', 42)).toBe(42);
    });

    test('returns undefined for missing property without default', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: { title: 'Test Task' },
      };

      expect(getComponentProp(props, 'status')).toBeUndefined();
    });

    test('handles empty data object', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: {},
      };

      expect(getComponentProp(props, 'title', 'Default')).toBe('Default');
    });

    test('handles nested objects correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.TaskCard',
        data: {
          nested: { value: 'test' },
        },
      };

      const nested = getComponentProp(props, 'nested');
      expect(nested).toEqual({ value: 'test' });
    });

    test('handles arrays correctly', () => {
      const props: A2UIProps = {
        type: 'a2ui.TestResults',
        data: {
          testCases: ['test1', 'test2', 'test3'],
        },
      };

      const testCases = getComponentProp(props, 'testCases', []);
      expect(testCases).toEqual(['test1', 'test2', 'test3']);
    });
  });

  describe('getAllComponentTypes()', () => {
    test('returns array of all component types', () => {
      const types = getAllComponentTypes();
      expect(Array.isArray(types)).toBe(true);
      expect(types.length).toBe(9);
    });

    test('returns a copy, not the original array', () => {
      const types1 = getAllComponentTypes();
      const types2 = getAllComponentTypes();
      expect(types1).not.toBe(types2);
      expect(types1).toEqual(types2);
    });

    test('returned array contains all expected types', () => {
      const types = getAllComponentTypes();
      expect(types).toContain('a2ui.TaskCard');
      expect(types).toContain('a2ui.ProgressRing');
      expect(types).toContain('a2ui.FileTree');
      expect(types).toContain('a2ui.TestResults');
      expect(types).toContain('a2ui.ActivityItem');
      expect(types).toContain('a2ui.ApprovalCard');
      expect(types).toContain('a2ui.DecisionCard');
      expect(types).toContain('a2ui.MilestoneCard');
      expect(types).toContain('a2ui.ErrorCard');
    });
  });

  describe('getComponentCount()', () => {
    test('returns correct count of components', () => {
      expect(getComponentCount()).toBe(9);
    });

    test('count matches catalog size', () => {
      const catalogSize = Object.keys(a2uiCatalog).length;
      expect(getComponentCount()).toBe(catalogSize);
    });

    test('count matches registeredComponentTypes length', () => {
      expect(getComponentCount()).toBe(registeredComponentTypes.length);
    });
  });

  describe('isCatalogValid()', () => {
    test('returns true for properly initialized catalog', () => {
      expect(isCatalogValid()).toBe(true);
    });

    test('validates all components are registered', () => {
      const isValid = isCatalogValid();
      expect(isValid).toBe(true);

      // Double-check each component individually
      registeredComponentTypes.forEach(type => {
        expect(validateComponentType(type)).toBe(true);
      });
    });
  });

  describe('Security Tests', () => {
    test('rejects prototype pollution attempts', () => {
      expect(validateComponentType('__proto__')).toBe(false);
      expect(validateComponentType('constructor')).toBe(false);
      expect(validateComponentType('prototype')).toBe(false);
      expect(getComponent('__proto__')).toBeUndefined();
    });

    test('rejects SQL injection-like inputs', () => {
      expect(validateComponentType("a2ui.TaskCard'; DROP TABLE--")).toBe(false);
      expect(validateComponentType('1=1')).toBe(false);
    });

    test('rejects XSS-like inputs', () => {
      expect(validateComponentType('<script>alert(1)</script>')).toBe(false);
      expect(validateComponentType('javascript:void(0)')).toBe(false);
    });

    test('rejects path traversal attempts', () => {
      expect(validateComponentType('../../../etc/passwd')).toBe(false);
      expect(validateComponentType('../../component')).toBe(false);
    });
  });
});

describe('A2UI Types', () => {
  describe('A2UIEventType enum', () => {
    test('contains expected event types', () => {
      expect(A2UIEventType.CLICK).toBe('click');
      expect(A2UIEventType.SUBMIT).toBe('submit');
      expect(A2UIEventType.CANCEL).toBe('cancel');
      expect(A2UIEventType.APPROVE).toBe('approve');
      expect(A2UIEventType.REJECT).toBe('reject');
      expect(A2UIEventType.EXPAND).toBe('expand');
      expect(A2UIEventType.COLLAPSE).toBe('collapse');
      expect(A2UIEventType.SELECT).toBe('select');
      expect(A2UIEventType.CHANGE).toBe('change');
    });
  });

  describe('A2UIMessageType enum', () => {
    test('contains expected message types', () => {
      expect(A2UIMessageType.COMMAND).toBe('command');
      expect(A2UIMessageType.QUERY).toBe('query');
      expect(A2UIMessageType.NOTIFICATION).toBe('notification');
      expect(A2UIMessageType.ERROR).toBe('error');
      expect(A2UIMessageType.SUCCESS).toBe('success');
    });
  });
});

describe('Component Integration Tests', () => {
  test('each component type can be retrieved and used', () => {
    registeredComponentTypes.forEach(type => {
      expect(validateComponentType(type)).toBe(true);

      const Component = getComponent(type);
      expect(Component).toBeDefined();
      expect(typeof Component).toBe('function');
    });
  });

  test('component retrieval workflow', () => {
    // Simulate the workflow of validating and retrieving a component
    const requestedType = 'a2ui.TaskCard';

    // Step 1: Validate
    const isValid = validateComponentType(requestedType);
    expect(isValid).toBe(true);

    // Step 2: Retrieve
    const Component = getComponent(requestedType);
    expect(Component).toBeDefined();

    // Step 3: Use
    expect(typeof Component).toBe('function');
  });

  test('invalid component workflow', () => {
    const requestedType = 'a2ui.Invalid';

    // Step 1: Validate
    const isValid = validateComponentType(requestedType);
    expect(isValid).toBe(false);

    // Step 2: Retrieve
    const Component = getComponent(requestedType);
    expect(Component).toBeUndefined();
  });
});
