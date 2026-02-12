/**
 * Theme Configuration Tests
 */

import { describe, it, expect } from 'vitest';
import { theme, themeClasses, checkContrast } from './theme';

describe('Theme Configuration', () => {
  it('should export theme object with all required sections', () => {
    expect(theme).toBeDefined();
    expect(theme.background).toBeDefined();
    expect(theme.text).toBeDefined();
    expect(theme.border).toBeDefined();
    expect(theme.status).toBeDefined();
    expect(theme.spacing).toBeDefined();
    expect(theme.radius).toBeDefined();
    expect(theme.shadow).toBeDefined();
    expect(theme.typography).toBeDefined();
    expect(theme.transition).toBeDefined();
    expect(theme.zIndex).toBeDefined();
  });

  it('should have valid HSL color values', () => {
    expect(theme.background.primary).toMatch(/hsl\(\d+\.?\d*, \d+\.?\d*%, \d+\.?\d*%\)/);
    expect(theme.text.primary).toMatch(/hsl\(\d+\.?\d*, \d+\.?\d*%, \d+\.?\d*%\)/);
    expect(theme.border.default).toMatch(/hsl\(\d+\.?\d*, \d+\.?\d*%, \d+\.?\d*%\)/);
  });

  it('should have all status colors defined', () => {
    const statuses = ['success', 'warning', 'error', 'info', 'pending'] as const;

    statuses.forEach(status => {
      expect(theme.status[status]).toBeDefined();
      expect(theme.status[status].bg).toBeDefined();
      expect(theme.status[status].text).toBeDefined();
      expect(theme.status[status].border).toBeDefined();
      expect(theme.status[status].bgSubtle).toBeDefined();
    });
  });

  it('should have consistent spacing scale (4px base)', () => {
    expect(theme.spacing.xs).toBe('0.25rem'); // 4px
    expect(theme.spacing.sm).toBe('0.5rem');  // 8px
    expect(theme.spacing.md).toBe('1rem');    // 16px
    expect(theme.spacing.lg).toBe('1.5rem'); // 24px
    expect(theme.spacing.xl).toBe('2rem');    // 32px
  });

  it('should have valid transition durations', () => {
    expect(theme.transition.fast).toBe('100ms');
    expect(theme.transition.normal).toBe('200ms');
    expect(theme.transition.slow).toBe('300ms');
    expect(theme.transition.slower).toBe('500ms');
  });

  it('should have typography sizes in ascending order', () => {
    const sizes = Object.values(theme.typography.fontSize);
    const numericSizes = sizes.map(size => parseFloat(size));

    for (let i = 1; i < numericSizes.length; i++) {
      expect(numericSizes[i]).toBeGreaterThanOrEqual(numericSizes[i - 1]);
    }
  });
});

describe('Theme Classes', () => {
  it('should export themeClasses object', () => {
    expect(themeClasses).toBeDefined();
    expect(themeClasses.card).toBeDefined();
    expect(themeClasses.button).toBeDefined();
    expect(themeClasses.input).toBeDefined();
    expect(themeClasses.text).toBeDefined();
  });

  it('should have card classes with proper Tailwind syntax', () => {
    expect(themeClasses.card.base).toContain('bg-');
    expect(themeClasses.card.base).toContain('border');
    expect(themeClasses.card.base).toContain('rounded');
    expect(themeClasses.card.hover).toContain('hover:');
    expect(themeClasses.card.focus).toContain('focus-within:');
  });

  it('should have button classes with transitions', () => {
    expect(themeClasses.button.base).toContain('transition');
    expect(themeClasses.button.focus).toContain('focus-visible:ring');
    expect(themeClasses.button.disabled).toContain('disabled:');
  });
});

describe('Contrast Checker', () => {
  it('should return contrast ratio and WCAG compliance', () => {
    const result = checkContrast('#ffffff', '#000000');

    expect(result).toHaveProperty('ratio');
    expect(result).toHaveProperty('passesAA');
    expect(result).toHaveProperty('passesAAA');
    expect(typeof result.ratio).toBe('number');
    expect(typeof result.passesAA).toBe('boolean');
    expect(typeof result.passesAAA).toBe('boolean');
  });

  it('should indicate our theme passes WCAG AA', () => {
    const result = checkContrast(theme.text.primary, theme.background.primary);

    expect(result.passesAA).toBe(true);
    expect(result.ratio).toBeGreaterThanOrEqual(4.5);
  });
});
