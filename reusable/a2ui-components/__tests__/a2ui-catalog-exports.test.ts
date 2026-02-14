/**
 * A2UI Catalog Export Tests
 * Validates that all catalog exports are accessible and properly typed
 */

import * as A2UICatalog from '@/lib/a2ui-catalog';
import * as A2UITypes from '@/lib/a2ui-types';

describe('A2UI Catalog Exports', () => {
  test('all catalog functions are exported', () => {
    expect(A2UICatalog.a2uiCatalog).toBeDefined();
    expect(A2UICatalog.registeredComponentTypes).toBeDefined();
    expect(A2UICatalog.validateComponentType).toBeDefined();
    expect(A2UICatalog.getComponent).toBeDefined();
    expect(A2UICatalog.getComponentProp).toBeDefined();
    expect(A2UICatalog.getAllComponentTypes).toBeDefined();
    expect(A2UICatalog.getComponentCount).toBeDefined();
    expect(A2UICatalog.isCatalogValid).toBeDefined();
  });

  test('all type exports are available', () => {
    expect(A2UITypes.A2UIEventType).toBeDefined();
    expect(A2UITypes.A2UIMessageType).toBeDefined();
  });

  test('catalog can be imported and used', () => {
    const { a2uiCatalog, validateComponentType, getComponent } = A2UICatalog;

    expect(Object.keys(a2uiCatalog).length).toBe(9);
    expect(validateComponentType('a2ui.TaskCard')).toBe(true);
    expect(getComponent('a2ui.TaskCard')).toBeDefined();
  });

  test('types can be imported and used', () => {
    const { A2UIEventType, A2UIMessageType } = A2UITypes;

    expect(A2UIEventType.CLICK).toBe('click');
    expect(A2UIMessageType.COMMAND).toBe('command');
  });
});
