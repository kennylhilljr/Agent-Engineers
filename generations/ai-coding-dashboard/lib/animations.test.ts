/**
 * Animation Presets Tests
 */

import { describe, it, expect } from 'vitest';
import {
  easings,
  fadeIn,
  slideUp,
  slideDown,
  scaleIn,
  pulse,
  bounce,
  shake,
  staggerContainer,
  staggerItem,
  expandCollapse,
  hoverLift,
  shimmer,
  backdrop,
  notificationSlide,
  progressFill,
  rotate,
  presets,
} from './animations';

describe('Animation Easings', () => {
  it('should export easing curves', () => {
    expect(easings).toBeDefined();
    expect(easings.easeOut).toBeDefined();
    expect(easings.easeIn).toBeDefined();
    expect(easings.easeInOut).toBeDefined();
    expect(easings.spring).toBeDefined();
    expect(easings.springBouncy).toBeDefined();
  });

  it('should have valid cubic-bezier values', () => {
    expect(easings.easeOut).toHaveLength(4);
    expect(easings.easeIn).toHaveLength(4);
    expect(easings.easeInOut).toHaveLength(4);
  });

  it('should have spring configurations', () => {
    expect(easings.spring.type).toBe('spring');
    expect(easings.spring.stiffness).toBeDefined();
    expect(easings.spring.damping).toBeDefined();
  });
});

describe('Fade Animation', () => {
  it('should have initial, animate, and exit states', () => {
    expect(fadeIn).toHaveProperty('initial');
    expect(fadeIn).toHaveProperty('animate');
    expect(fadeIn).toHaveProperty('exit');
  });

  it('should fade from 0 to 1 opacity', () => {
    expect(fadeIn.initial).toHaveProperty('opacity', 0);
    expect(fadeIn.animate).toHaveProperty('opacity', 1);
  });

  it('should have transition configuration', () => {
    expect(fadeIn.animate).toHaveProperty('transition');
    expect(fadeIn.animate.transition).toHaveProperty('duration');
  });
});

describe('Slide Animations', () => {
  it('should have slideUp variant', () => {
    expect(slideUp.initial).toHaveProperty('y', 20);
    expect(slideUp.animate).toHaveProperty('y', 0);
    expect(slideUp.initial).toHaveProperty('opacity', 0);
    expect(slideUp.animate).toHaveProperty('opacity', 1);
  });

  it('should have slideDown variant', () => {
    expect(slideDown.initial).toHaveProperty('y', -20);
    expect(slideDown.animate).toHaveProperty('y', 0);
  });
});

describe('Scale Animation', () => {
  it('should scale from 0.95 to 1', () => {
    expect(scaleIn.initial).toHaveProperty('scale', 0.95);
    expect(scaleIn.animate).toHaveProperty('scale', 1);
    expect(scaleIn.initial).toHaveProperty('opacity', 0);
    expect(scaleIn.animate).toHaveProperty('opacity', 1);
  });
});

describe('Pulse Animation', () => {
  it('should have infinite repeat configuration', () => {
    expect(pulse.animate.transition).toHaveProperty('repeat', Infinity);
    expect(pulse.animate.transition).toHaveProperty('repeatType', 'reverse');
  });

  it('should pulse between scale values', () => {
    expect(pulse.initial).toHaveProperty('scale', 1);
    expect(pulse.animate).toHaveProperty('scale', 1.02);
  });
});

describe('Bounce Animation', () => {
  it('should have keyframe array for scale', () => {
    expect(Array.isArray(bounce.animate.scale)).toBe(true);
    expect(bounce.animate.scale).toHaveLength(5);
  });

  it('should start from 0 and end at 1', () => {
    expect(bounce.initial.scale).toBe(0);
    expect(bounce.animate.scale[4]).toBe(1);
  });
});

describe('Shake Animation', () => {
  it('should have x-axis movement keyframes', () => {
    expect(Array.isArray(shake.animate.x)).toBe(true);
    expect(shake.initial.x).toBe(0);
    expect(shake.animate.x[0]).toBe(0);
    expect(shake.animate.x[shake.animate.x.length - 1]).toBe(0);
  });
});

describe('Stagger Animations', () => {
  it('should have stagger configuration in container', () => {
    expect(staggerContainer.animate.transition).toHaveProperty('staggerChildren');
    expect(staggerContainer.animate.transition.staggerChildren).toBe(0.05);
  });

  it('should have item animation', () => {
    expect(staggerItem.initial).toHaveProperty('opacity', 0);
    expect(staggerItem.initial).toHaveProperty('y', 10);
    expect(staggerItem.animate).toHaveProperty('opacity', 1);
    expect(staggerItem.animate).toHaveProperty('y', 0);
  });
});

describe('Expand/Collapse Animation', () => {
  it('should have collapsed and expanded states', () => {
    expect(expandCollapse).toHaveProperty('collapsed');
    expect(expandCollapse).toHaveProperty('expanded');
  });

  it('should animate height', () => {
    expect(expandCollapse.collapsed).toHaveProperty('height', 0);
    expect(expandCollapse.expanded).toHaveProperty('height', 'auto');
  });
});

describe('Hover Lift', () => {
  it('should have rest, hover, and tap states', () => {
    expect(hoverLift).toHaveProperty('rest');
    expect(hoverLift).toHaveProperty('hover');
    expect(hoverLift).toHaveProperty('tap');
  });

  it('should lift element on hover', () => {
    expect(hoverLift.rest.y).toBe(0);
    expect(hoverLift.hover.y).toBe(-2);
    expect(hoverLift.hover.scale).toBe(1.02);
  });
});

describe('Shimmer Animation', () => {
  it('should animate background position', () => {
    expect(shimmer.initial).toHaveProperty('backgroundPosition');
    expect(shimmer.animate).toHaveProperty('backgroundPosition');
  });

  it('should repeat infinitely', () => {
    expect(shimmer.animate.transition).toHaveProperty('repeat', Infinity);
  });
});

describe('Progress Fill', () => {
  it('should return animation based on progress value', () => {
    const anim = progressFill(75);
    expect(anim.initial).toHaveProperty('width', '0%');
    expect(anim.animate).toHaveProperty('width', '75%');
  });

  it('should handle 0% progress', () => {
    const anim = progressFill(0);
    expect(anim.animate.width).toBe('0%');
  });

  it('should handle 100% progress', () => {
    const anim = progressFill(100);
    expect(anim.animate.width).toBe('100%');
  });
});

describe('Rotate Animation', () => {
  it('should rotate 360 degrees infinitely', () => {
    expect(rotate.animate).toHaveProperty('rotate', 360);
    expect(rotate.animate.transition).toHaveProperty('repeat', Infinity);
    expect(rotate.animate.transition).toHaveProperty('ease', 'linear');
  });
});

describe('Animation Presets', () => {
  it('should export all presets', () => {
    expect(presets).toBeDefined();
    expect(presets.card).toBe(scaleIn);
    expect(presets.modal).toBe(scaleIn);
    expect(presets.toast).toBe(notificationSlide);
    expect(presets.list).toBe(staggerContainer);
    expect(presets.listItem).toBe(staggerItem);
    expect(presets.button).toBe(hoverLift);
    expect(presets.skeleton).toBe(shimmer);
    expect(presets.loader).toBe(pulse);
    expect(presets.success).toBe(bounce);
    expect(presets.error).toBe(shake);
  });

  it('should have consistent naming', () => {
    const presetNames = Object.keys(presets);
    expect(presetNames).toContain('fadeIn');
    expect(presetNames).toContain('slideUp');
    expect(presetNames).toContain('slideDown');
  });
});
