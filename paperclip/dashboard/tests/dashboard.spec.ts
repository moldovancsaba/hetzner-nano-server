import { test, expect } from '@playwright/test';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const axePath = require.resolve('axe-core/axe.min.js');
const snapshot = {
  schema_version: '1.1', as_of: new Date().toISOString(), observed_through: new Date().toISOString(), coverage: 'partial',
  clients: [{ scope: { application: 'classscout', client: 'NYC' }, paperclip: { source_offers: 2, coverage: 'source-offers-only' }, exchange: { unprocessed: 2, oldest_pending_seconds: 45 }, openclaw: { qualified: null, accepted_operations: 1, destination_confirmed: 0, public_listings: 0, uncertain_evaluations: 1, observed_through: null, coverage: 'not_measured' }, next_action: null }],
};
test('keyboard operation, explicit missing evidence and automated accessibility', async ({ page }) => {
  await page.route('**/factory/exchange-snapshot', route => route.fulfill({ json: snapshot }));
  await page.goto('/factory/exchange/');
  await expect(page.getByRole('heading', { name: 'Paperclip and OpenClaw results' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'NYC', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Not measured', exact: true }).first()).toBeVisible();
  await page.keyboard.press('Tab');await expect(page.getByRole('link', { name: 'Skip to results' })).toBeFocused();
  await page.keyboard.press('Enter');await expect(page.locator('#results')).toBeFocused();
  await page.getByRole('button', { name: 'Refresh results' }).focus();await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Refresh results' })).toBeFocused();
  await page.addScriptTag({ path: axePath });
  const violations = await page.evaluate(async () => {
    const engine = (window as unknown as { axe: { run: (v: unknown, o: unknown) => Promise<{ violations: { id: string; impact: string }[] }> } }).axe;
    return (await engine.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } })).violations;
  });
  expect(violations).toEqual([]);
  await page.screenshot({ path: '/tmp/paperclip-exchange-dashboard.png', fullPage: true });
});
test('error and stale content remain explicit at narrow width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active' });
  await page.route('**/factory/exchange-snapshot', route => route.fulfill({ status: 503, json: { error: 'unavailable' } }));
  await page.goto('/factory/exchange/');
  await expect(page.getByRole('alert')).toContainText('exchange is unavailable');
  await expect(page.getByRole('button', { name: 'Refresh results' })).toBeEnabled();
  await page.screenshot({ path: '/tmp/paperclip-exchange-dashboard-error.png', fullPage: true });
});
test('dark mode empty state, stale warning and malformed refresh retain verified results', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  let result: unknown = { ...snapshot, clients: [] };
  await page.route('**/factory/exchange-snapshot', route => route.fulfill({ json: result }));
  await page.goto('/factory/exchange/');
  await expect(page.getByText('No enrolled client results')).toBeVisible();
  result = { ...snapshot, observed_through: '2020-01-01T00:00:00Z' };
  await page.getByRole('button', { name: 'Refresh results' }).click();
  await expect(page.getByText('Older results', { exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'NYC', exact: true })).toBeVisible();
  result = { ...snapshot, clients: [{ ...snapshot.clients[0], openclaw: { ...snapshot.clients[0].openclaw, accepted_operations: -1 } }] };
  await page.getByRole('button', { name: 'Refresh results' }).click();
  await expect(page.getByRole('alert')).toContainText('format is not supported');
  await expect(page.getByRole('cell', { name: 'NYC', exact: true })).toBeVisible();
});
test('delivery history separates durable intake, causal waits and nonpublic readback',async({page})=>{
  const at=new Date().toISOString();
  const base={occurred_at:at,reference:'fixture-reference',reason_code:null,qualified:null,publication:null,readback_result:null};
  const client={...snapshot.clients[0],exchange:{...snapshot.clients[0].exchange,events_waiting:1},openclaw:{...snapshot.clients[0].openclaw,coverage:'events-only'},timeline:[
    {...base,id:'offer:fixture',phase:'source_offered'},
    {...base,id:'intake:fixture',phase:'intake_received'},
    {...base,id:'event:pending',phase:'feedback_waiting',reason_code:'awaiting_predecessor'},
    {...base,id:'event:readback',phase:'delivery_readback',publication:'not_public',readback_result:'found_matching'},
  ]};
  await page.route('**/factory/exchange-snapshot',route=>route.fulfill({json:{...snapshot,clients:[client]}}));
  await page.goto('/factory/exchange/');
  for(const name of ['Source offered','Intake saved','Feedback awaiting earlier evidence','Verified not public','found matching'])await expect(page.getByRole('cell',{name,exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'NYC delivery history'})).toBeVisible();
  await page.addScriptTag({path:axePath});
  const result=await page.evaluate(async()=>(window as unknown as {axe:{run:(v:unknown,o:unknown)=>Promise<{violations:unknown[]}>}}).axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
  expect(result.violations).toEqual([]);
});
