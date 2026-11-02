import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests', workers: 1, fullyParallel: false,
  use: { baseURL: 'http://127.0.0.1:4173', launchOptions: { executablePath: process.env.CHROMIUM_EXECUTABLE } },
  webServer: { command: 'npx vite preview --host 127.0.0.1 --port 4173', port: 4173, reuseExistingServer: false },
});
