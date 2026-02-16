module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testMatch: ['**/__tests__/**/*.test.js'],
  moduleFileExtensions: ['js', 'json'],
  collectCoverageFrom: [
    'dashboard/**/*.js',
    '!dashboard/**/*.test.js'
  ],
  coveragePathIgnorePatterns: [
    '/node_modules/',
    '/test-results/'
  ]
};
