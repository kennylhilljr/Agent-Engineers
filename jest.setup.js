/**
 * Jest setup file for localStorage and other browser APIs
 */

// Import jest-dom matchers
require('@testing-library/jest-dom');

// Real localStorage implementation for tests that need it
class RealLocalStorage {
  constructor() {
    this.store = {};
  }

  getItem(key) {
    return this.store[key] || null;
  }

  setItem(key, value) {
    this.store[key] = String(value);
  }

  removeItem(key) {
    delete this.store[key];
  }

  clear() {
    this.store = {};
  }

  key(index) {
    return Object.keys(this.store)[index] || null;
  }

  get length() {
    return Object.keys(this.store).length;
  }
}

// Export for use in tests
global.RealLocalStorage = RealLocalStorage;

// Setup default console mocks
jest.spyOn(console, 'log').mockImplementation(() => {});
jest.spyOn(console, 'warn').mockImplementation(() => {});
jest.spyOn(console, 'error').mockImplementation(() => {});

// Polyfill Blob for jsdom
if (typeof Blob === 'undefined') {
  global.Blob = class Blob {
    constructor(parts = [], options = {}) {
      this.size = parts.reduce((acc, part) => acc + (typeof part === 'string' ? part.length : part.size), 0);
      this.type = options.type || '';
    }
  };
}
