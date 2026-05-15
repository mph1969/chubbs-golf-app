// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * Playwright config for Chubbs E2E tests.
 *
 * Tests run against the LIVE Netlify deployment by default
 * (chubbs-golf.netlify.app). Use BASE_URL env to override for local
 * dev or staging deploys. Tests should never write to a LIVE event;
 * the EVENT_ID below points at a dedicated test bundle.
 *
 * Run:
 *   npm test                 # headless
 *   npm run test:headed      # see the browsers actually open
 *   npm run test:debug       # step through with the Playwright inspector
 *   npm run report           # open the last HTML report
 */

const BASE_URL = process.env.BASE_URL || 'https://chubbs-golf.netlify.app';
const EVENT_ID = process.env.EVENT_ID || '2026-TEST5-Brai';

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60_000,         // per-test ceiling — generous because each test
                           // spawns ~4 browser contexts in parallel
  expect: { timeout: 10_000 },
  fullyParallel: false,    // tests are mostly stateless but the in-app
                           // Firebase sync can clobber siblings if they race
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: 'desktop-chrome',
      use: { ...devices['Desktop Chrome'] },
    },
    // Mobile project — emulates iPhone viewport so we can confirm the
    // header-compaction (.hero.event-loaded) lands the scoring grid above
    // the fold. Doesn't actually run on iOS Safari (Playwright uses WebKit
    // engine but not iOS device chrome), but catches WebKit-specific bugs
    // that don't repro on Chromium.
    {
      name: 'mobile-webkit',
      use: { ...devices['iPhone 13'] },
    },
  ],
});

module.exports.EVENT_ID = EVENT_ID;
