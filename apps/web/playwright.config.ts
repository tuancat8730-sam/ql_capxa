import { defineConfig, devices } from '@playwright/test'

const reuse = !process.env.CI

// The projects share one database, so they run one after another (workers: 1) and every test
// makes the data it writes unique per project.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173', trace: 'on-first-retry' },
  projects: [
    { name: 'mobile', use: { ...devices['Pixel 5'] } },
    // iPad Mini screen and touch, in Chromium so one browser install covers every project
    { name: 'tablet', use: { ...devices['iPad Mini'], defaultBrowserType: 'chromium' } },
    { name: 'desktop', use: { viewport: { width: 1280, height: 800 } } },
  ],
  webServer: [
    {
      // fresh database + moto S3 + API (needs the compose `db` service)
      command: 'bash ../../scripts/e2e-stack.sh',
      url: 'http://localhost:8000/api/v1/health',
      reuseExistingServer: reuse,
      timeout: 180_000,
    },
    { command: 'pnpm dev', url: 'http://localhost:5173', reuseExistingServer: reuse },
  ],
})
