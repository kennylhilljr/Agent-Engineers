/**
 * Animation Presets with Framer Motion
 * Reusable animation configurations for consistent motion design
 */

import { Variants } from 'framer-motion';

// Easing curves
export const easings = {
  easeOut: [0.0, 0.0, 0.2, 1],
  easeIn: [0.4, 0.0, 1, 1],
  easeInOut: [0.4, 0.0, 0.2, 1],
  spring: { type: 'spring', stiffness: 300, damping: 30 },
  springBouncy: { type: 'spring', stiffness: 400, damping: 20 },
} as const;

// Fade in animation
export const fadeIn: Variants = {
  initial: {
    opacity: 0,
  },
  animate: {
    opacity: 1,
    transition: {
      duration: 0.2,
      ease: easings.easeOut,
    },
  },
  exit: {
    opacity: 0,
    transition: {
      duration: 0.15,
      ease: easings.easeIn,
    },
  },
};

// Slide up from bottom
export const slideUp: Variants = {
  initial: {
    opacity: 0,
    y: 20,
  },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
      ease: easings.easeOut,
    },
  },
  exit: {
    opacity: 0,
    y: 10,
    transition: {
      duration: 0.2,
      ease: easings.easeIn,
    },
  },
};

// Slide down from top
export const slideDown: Variants = {
  initial: {
    opacity: 0,
    y: -20,
  },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
      ease: easings.easeOut,
    },
  },
  exit: {
    opacity: 0,
    y: -10,
    transition: {
      duration: 0.2,
      ease: easings.easeIn,
    },
  },
};

// Scale in from center
export const scaleIn: Variants = {
  initial: {
    opacity: 0,
    scale: 0.95,
  },
  animate: {
    opacity: 1,
    scale: 1,
    transition: {
      duration: 0.2,
      ease: easings.easeOut,
    },
  },
  exit: {
    opacity: 0,
    scale: 0.95,
    transition: {
      duration: 0.15,
      ease: easings.easeIn,
    },
  },
};

// Pulse for loading states
export const pulse: Variants = {
  initial: {
    opacity: 0.6,
    scale: 1,
  },
  animate: {
    opacity: 1,
    scale: 1.02,
    transition: {
      duration: 0.8,
      repeat: Infinity,
      repeatType: 'reverse',
      ease: easings.easeInOut,
    },
  },
};

// Bounce for achievements/success
export const bounce: Variants = {
  initial: {
    scale: 0,
  },
  animate: {
    scale: [0, 1.1, 0.9, 1.05, 1],
    transition: {
      duration: 0.6,
      times: [0, 0.4, 0.6, 0.8, 1],
      ease: easings.easeOut,
    },
  },
};

// Shake for errors
export const shake: Variants = {
  initial: {
    x: 0,
  },
  animate: {
    x: [0, -10, 10, -10, 10, 0],
    transition: {
      duration: 0.4,
      times: [0, 0.2, 0.4, 0.6, 0.8, 1],
    },
  },
};

// Stagger children animations
export const staggerContainer: Variants = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1,
    },
  },
};

export const staggerItem: Variants = {
  initial: {
    opacity: 0,
    y: 10,
  },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
      ease: easings.easeOut,
    },
  },
};

// Expand/collapse for accordions
export const expandCollapse: Variants = {
  collapsed: {
    height: 0,
    opacity: 0,
    transition: {
      duration: 0.2,
      ease: easings.easeInOut,
    },
  },
  expanded: {
    height: 'auto',
    opacity: 1,
    transition: {
      duration: 0.3,
      ease: easings.easeOut,
    },
  },
};

// Hover lift effect
export const hoverLift = {
  rest: {
    scale: 1,
    y: 0,
  },
  hover: {
    scale: 1.02,
    y: -2,
    transition: {
      duration: 0.2,
      ease: easings.easeOut,
    },
  },
  tap: {
    scale: 0.98,
    y: 0,
  },
};

// Skeleton shimmer effect
export const shimmer: Variants = {
  initial: {
    backgroundPosition: '-200% 0',
  },
  animate: {
    backgroundPosition: '200% 0',
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: 'linear',
    },
  },
};

// Modal/dialog backdrop
export const backdrop: Variants = {
  initial: {
    opacity: 0,
  },
  animate: {
    opacity: 1,
    transition: {
      duration: 0.2,
    },
  },
  exit: {
    opacity: 0,
    transition: {
      duration: 0.2,
    },
  },
};

// Notification slide in from right
export const notificationSlide: Variants = {
  initial: {
    x: 400,
    opacity: 0,
  },
  animate: {
    x: 0,
    opacity: 1,
    transition: {
      duration: 0.3,
      ease: easings.easeOut,
    },
  },
  exit: {
    x: 400,
    opacity: 0,
    transition: {
      duration: 0.2,
      ease: easings.easeIn,
    },
  },
};

// Progress bar fill animation
export const progressFill = (progress: number) => ({
  initial: {
    width: '0%',
  },
  animate: {
    width: `${progress}%`,
    transition: {
      duration: 0.5,
      ease: easings.easeOut,
    },
  },
});

// Rotation for loading spinners
export const rotate: Variants = {
  animate: {
    rotate: 360,
    transition: {
      duration: 1,
      repeat: Infinity,
      ease: 'linear',
    },
  },
};

// Preset combinations for common use cases
export const presets = {
  card: scaleIn,
  modal: scaleIn,
  toast: notificationSlide,
  list: staggerContainer,
  listItem: staggerItem,
  button: hoverLift,
  skeleton: shimmer,
  loader: pulse,
  success: bounce,
  error: shake,
  fadeIn,
  slideUp,
  slideDown,
} as const;

export type AnimationPreset = keyof typeof presets;
