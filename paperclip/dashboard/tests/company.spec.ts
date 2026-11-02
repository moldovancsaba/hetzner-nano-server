import { test, expect } from '@playwright/test';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const axePath = require.resolve('axe-core/axe.min.js');
const indexPath = fileURLToPath(new URL('../dist/index.html', import.meta.url));
const fixture = {
  updated_at: new Date().toISOString(), mode: 'Standard',
  funnel: { published: 2, updates_verified: 1, research_drafts: 3, source_checked: 2, needs_evidence: 1, writes_uncertain: 0 },
  operations: { team_available: true, task_counts: { in_progress: 1, blocked: 0 }, model_waits: 0, writes_today: 1, runs_24h: { completed: 2, blocked: 0, failed: 0 }, completion_rate_24h: 100, median_run_seconds_24h: 2,
    projects: [{ name: 'ClassScout', url: '/NAR/projects/fixture', mode: 'Research', queued: 1, working: 1, review: 0, blocked: 0, done_24h: 2 }],
    team: [{ name: 'Research', url: '/NAR/agents/fixture', status: 'idle', assigned: 1, blocked: 0, completed_24h: 2, last_run_at: null, last_outcome: 'completed' }],
    activity: [{ identifier: 'NAR-FIXTURE', title: 'Checked evidence', url: '/NAR/issues/NAR-FIXTURE', role: 'research', outcome: 'completed', at: null }], upcoming: [] },
  inference: { models: ['fixture'], contexts: [], tokens_24h: 0, generation_slots: 1, recorded_calls_24h: 0, billing: 'Free local models' },
  delivery: { waiting_evidence_count: 0, owner_attention_count: 0, blocked_details: [], coordination: {}, knowledge: {}, freshness: {}, automation: {}, backup: { status: 'Not measured' }, sales: {}, engines: {}, program_updates: {}, padel_intake: {} },
  blocked: [], by_market: [], search_budget: {}, remote_llm: { enabled: false }, daily_write_limit: 20, recovery: { attempts: 1, fields_recovered: 1 }, padel: {},
};
test('GDS company shell preserves native operating views and keyboard accessibility', async ({ page }) => {
  await page.route('**/factory/', route => route.fulfill({ path: indexPath, contentType: 'text/html' }));
  await page.route('**/factory/metrics', route => route.fulfill({ json: fixture }));
  await page.goto('/factory/');
  await expect(page.getByRole('heading', { name: 'Company overview', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'ClassScout', exact: true })).toBeVisible();
  for (const name of ['Team and workload','Waiting and reviews','Recent work','ClassScout coverage','Model usage','Publishing effectiveness','Search allowance','Recovery backups','Client connections']) await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await page.keyboard.press('Tab');await expect(page.getByRole('link', { name: 'Skip to company results' })).toBeFocused();
  await page.keyboard.press('Enter');await expect(page.locator('#company-results')).toBeFocused();
  const detail=page.getByRole('button',{name:'Model usage',exact:true});await detail.focus();await page.keyboard.press('Space');
  await expect(detail).toHaveAttribute('aria-expanded','true');await expect(page.getByRole('cell',{name:'fixture',exact:true})).toBeVisible();
  await page.addScriptTag({ path: axePath });
  const violations = await page.evaluate(async () => (window as unknown as { axe: { run: (v: unknown, o: unknown) => Promise<{ violations: unknown[] }> } }).axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21aa'] } }));
  expect(violations.violations).toEqual([]);
  await page.screenshot({ path: '/tmp/paperclip-company-gds.png', fullPage: true });
});
test('company refresh retains data on error and refuses injected navigation', async ({ page }) => {
  let failed = false;
  await page.route('**/factory/', route => route.fulfill({ path: indexPath, contentType: 'text/html' }));
  await page.route('**/factory/metrics', route => failed ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ json: { ...fixture, operations: { ...fixture.operations, projects: [{ ...fixture.operations.projects[0], url: 'javascript:alert(1)' }] } } }));
  await page.setViewportSize({ width: 390, height: 844 });await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce', colorScheme: 'dark' });
  await page.goto('/factory/');await expect(page.getByRole('heading', { name: 'Native Paperclip results' })).toBeVisible();
  await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0);
  failed = true;await page.getByRole('button', { name: 'Refresh company results' }).click();
  await expect(page.getByRole('alert')).toContainText('temporarily unavailable');
  await expect(page.getByRole('heading', { name: 'Native Paperclip results' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Refresh company results' })).toBeEnabled();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
