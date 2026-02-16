/**
 * Playwright Configuration for Dashboard Server Tests
 */

module.exports = {
  testDir: './tests/dashboard',
  testMatch: '**/*.spec.js',
  timeout: 30000,
  expect: {
    timeout: 10000
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 1,
  reporter: [
    ['html', { outputFolder: 'test-results/html' }],
    ['json', { outputFile: 'test-results/results.json' }],
    ['list']
  ],
  use: {
    baseURL: 'http://127.0.0.1:8080',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium'
      }
    }
  ],
  webServer: {
    command: 'python -m dashboard.server --port 8080',
    url: 'http://127.0.0.1:8080/health',
    timeout: 120000,
    reuseExistingServer: !process.env.CI
  }
};
