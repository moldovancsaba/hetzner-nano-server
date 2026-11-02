import { useEffect, useRef, useState } from 'react';
import { Anchor, BodyText, Box, Container, Group, PageTitle, SectionTitle, SemanticButton, SimpleDataTable, Stack, StateBlock } from '@sovereignsquad/gds/client';

type Client = {
  scope: { application: string; client: string };
  paperclip: { source_offers: number | null; coverage: string };
  exchange: { unprocessed: number | null; oldest_pending_seconds: number | null };
  openclaw: { qualified: number | null; accepted_operations: number | null; destination_confirmed: number | null; public_listings: number | null; uncertain_evaluations: number | null; observed_through: string | null; coverage: string };
  next_action: string | null;
};
export type Snapshot = { schema_version: string; as_of: string; observed_through: string; coverage: string; clients: Client[] };
const record = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const timestamp = (v: unknown) => typeof v === 'string' && v.length <= 64 && !Number.isNaN(Date.parse(v));
const count = (v: unknown) => v === null || (Number.isSafeInteger(v) && Number(v) >= 0);
const scopes: Record<string, string[]> = { classscout: ['NYC', 'BOS', 'LA'], salesleadgenerator: ['cogmap', 'seyu', 'dvsc'], management: ['padel-africa', 'sportolok'] };
export function parseSnapshot(raw: unknown): Snapshot {
  const fail = () => { throw new Error('The result format is not supported.'); };
  if (!record(raw) || raw.schema_version !== '1.1' || !timestamp(raw.as_of) || !timestamp(raw.observed_through) || !['partial','complete'].includes(String(raw.coverage)) || !Array.isArray(raw.clients) || raw.clients.length > 8) return fail();
  const seen = new Set<string>();
  for (const item of raw.clients) {
    if (!record(item) || !record(item.scope) || !record(item.paperclip) || !record(item.exchange) || !record(item.openclaw)) return fail();
    const { scope, paperclip, exchange, openclaw } = item;
    const key = `${scope.application}/${scope.client}`;
    if (typeof scope.application !== 'string' || typeof scope.client !== 'string' || !scopes[scope.application]?.includes(scope.client) || seen.has(key)) return fail();
    seen.add(key);
    if (!count(paperclip.source_offers) || !count(exchange.unprocessed) || !count(exchange.oldest_pending_seconds)) return fail();
    for (const field of ['qualified','accepted_operations','destination_confirmed','public_listings','uncertain_evaluations']) if (!count(openclaw[field])) return fail();
    if (openclaw.observed_through !== null && !timestamp(openclaw.observed_through)) return fail();
    if (!['source-offers-only','not_measured','complete'].includes(String(paperclip.coverage)) || !['events-only','not_measured','complete'].includes(String(openclaw.coverage))) return fail();
    if (item.next_action !== null && (typeof item.next_action !== 'string' || item.next_action.length > 1000)) return fail();
  }
  return raw as unknown as Snapshot;
}
async function boundedSnapshot(response: Response): Promise<Snapshot> {
  if (!response.body) throw new Error('The response contained no results.');
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 262144) { await reader.cancel(); throw new Error('The results exceeded the display limit.'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return parseSnapshot(JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)));
}
const value = (v: number | null | undefined) => v === null || v === undefined ? 'Not measured' : String(v);
const date = (v: string | null) => v ? new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Budapest' }).format(new Date(v)) : 'Not measured';

export function Dashboard() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updated, setUpdated] = useState(0);
  const current = useRef<AbortController | null>(null);
  async function refresh() {
    current.current?.abort();
    const controller = new AbortController(); current.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 10000);
    setLoading(true); setError(null);
    try {
      const response = await fetch('/factory/exchange-snapshot', { signal: controller.signal, credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) throw new Error(response.status === 503 ? 'The exchange is unavailable. Saved work remains queued.' : 'Results could not be loaded.');
      const next = await boundedSnapshot(response);
      if (current.current === controller) { setData(next);setUpdated(Date.now()); }
    } catch (cause) {
      if (current.current === controller) setError(cause instanceof Error && cause.name !== 'AbortError' ? cause.message : 'The request timed out. Retry when the connection is available.');
    } finally {
      clearTimeout(timer);
      if (current.current === controller) setLoading(false);
    }
  }
  useEffect(() => { void refresh(); return () => current.current?.abort(); }, []);
  const stale = data && Date.now() - Date.parse(data.observed_through) > 3600000;
  const rows = data?.clients.map((client) => ({
    key: `${client.scope.application}/${client.scope.client}`, client: client.scope.client,
    sources: value(client.paperclip.source_offers), qualified: value(client.openclaw.qualified),
    accepted: value(client.openclaw.accepted_operations), confirmed: value(client.openclaw.destination_confirmed), published: value(client.openclaw.public_listings),
    waiting: value(client.exchange.unprocessed), uncertain: value(client.openclaw.uncertain_evaluations),
    observed: date(client.openclaw.observed_through), action: client.next_action || (client.openclaw.coverage === 'not_measured' ? 'Awaiting verified processing evidence' : 'No action recorded'),
  })) || [];
  return <Container size="xl" py="xl"><Stack gap="xl">
    <Anchor href="#results">Skip to results</Anchor>
    <Box component="header"><Stack gap="sm"><PageTitle>Paperclip and OpenClaw results</PageTitle><BodyText>Follow source research, queued work and verified results for every enrolled client.</BodyText><Anchor href="/factory/">Company overview</Anchor></Stack></Box>
    <Box component="main" id="results" tabIndex={-1} aria-busy={loading}>
      <Stack gap="lg">
        <Group justify="space-between"><SectionTitle>Delivery overview</SectionTitle><SemanticButton action="refresh" aria-label="Refresh results" onClick={() => void refresh()} loading={loading} disabled={loading} /></Group>
        <Box role="status" aria-live="polite" aria-atomic="true"><BodyText>{loading ? 'Loading results…' : error ? 'Results could not be refreshed.' : updated ? 'Results updated.' : 'Results have not been loaded.'}</BodyText></Box>
        {error && <Box role="alert"><StateBlock variant="error" title="Results unavailable" description={error} /></Box>}
        {data && <BodyText>Snapshot {date(data.as_of)} Budapest. {data.coverage === 'partial' ? 'Coverage is partial; unmeasured values are shown explicitly.' : 'Coverage is complete.'} {stale ? 'This snapshot is stale.' : ''} Shared outcomes are counted once.</BodyText>}
        {stale && <StateBlock variant="empty" title="Older results" description="The last snapshot is more than an hour old. Refresh to check for current evidence." />}
        <SimpleDataTable loading={loading && !data} rows={rows} getRowKey={(row) => row.key} emptyTitle="No enrolled client results" emptyDescription="Results appear after an enrolled client exchanges and processes evidence." columns={[
          {key:'client',header:'Client'},{key:'sources',header:'Paperclip sources'},{key:'qualified',header:'Qualified'},
          {key:'accepted',header:'Accepted operations'},{key:'confirmed',header:'Confirmed changes'},{key:'published',header:'Public listings'},
          {key:'waiting',header:'Waiting'},{key:'uncertain',header:'Uncertain'},{key:'observed',header:'Processing observed through'},{key:'action',header:'Next action'},
        ]} />
        <BodyText>Accepted cards and private leads are separate from public listings. A received packet is not a qualified candidate. Unavailable measurements do not mean zero results.</BodyText>
      </Stack>
    </Box>
  </Stack></Container>;
}
