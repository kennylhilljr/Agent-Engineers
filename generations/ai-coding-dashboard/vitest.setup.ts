import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock all CSS imports to avoid loading errors
vi.mock('*.css', () => ({
  default: {},
}));

// Mock CopilotKit CSS specifically
vi.mock('katex/dist/katex.min.css', () => ({
  default: {},
}));
