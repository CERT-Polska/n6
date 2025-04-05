import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 2,
  workers: undefined,
  reporter: 'list',
  use: {
    baseURL: 'https://localhost',
    trace: 'on-first-retry',
    ignoreHTTPSErrors: true
  },
  timeout: 60_000,
  expect: { timeout: 20_000 },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ]
});
