import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 120000,
  outputDir: 'playwright-artifacts',
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    headless: true,
    baseURL: 'http://127.0.0.1:5173',
    screenshot: 'only-on-failure',
    video: 'on',
    trace: 'retain-on-failure',
  },
});
