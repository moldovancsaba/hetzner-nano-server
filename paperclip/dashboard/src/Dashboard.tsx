import { useEffect, useRef, useState } from 'react';
import { readBoundedJSON } from './data';
import { Anchor, BodyText, Box, Container, Group, PageTitle, SectionTitle, SemanticButton, SimpleDataTable, Stack, StateBlock } from '@sovereignsquad/gds/client';

const phases: Record<string, string> = { source_offered: 'Source offered', source_expired: 'Source offer expired', source_refused: 'Source offer refused', intake_received: 'Intake saved', queued: 'Queued', checked: 'Checked', not_checked: 'Not checked', rejected: 'Rejected', submission_accepted: 'Operation accepted', uncertain: 'Uncertain outcome', gap_report: 'Evidence gap reported', delivery_readback: 'Destination readback', feedback_waiting: 'Feedback awaiting earlier evidence' };
type Observation = { id: string; occurred_at: string; phase: string; reference: string; reason_code: string | null; qualified: boolean | null; publication: string | null; readback_result: string | null };
type Client = {
  scope: { application: string; client: string };
  paperclip: { source_offers: number | null; coverage: string };
  exchange: { unprocessed: number | null; oldest_pending_seconds: number | null; events_waiting?: number | null };
  openclaw: { qualified: number | null; accepted_operations: number | null; destination_confirmed: number | null; public_listings: number | null; uncertain_evaluations: number | null; observed_through: string | null; coverage: string };
  next_action: string | null;
  timeline?: Observation[];
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
    if ('events_waiting' in exchange && !count(exchange.events_waiting)) return fail();
    for (const field of ['qualified','accepted_operations','destination_confirmed','public_listings','uncertain_evaluations']) if (!count(openclaw[field])) return fail();
    if (openclaw.observed_through !== null && !timestamp(openclaw.observed_through)) return fail();
    if (!['source-offers-only','not_measured','complete'].includes(String(paperclip.coverage)) || !['events-only','not_measured','complete'].includes(String(openclaw.coverage))) return fail();
    if (item.next_action !== null && (typeof item.next_action !== 'string' || item.next_action.length > 1000)) return fail();
    if ('timeline' in item) {
      if (!Array.isArray(item.timeline) || item.timeline.length > 20) return fail();
      const identities = new Set<string>();
      for (const observation of item.timeline) {
        if (!record(observation) || typeof observation.id !== 'string' || !observation.id.length || observation.id.length > 160 || identities.has(observation.id) || !timestamp(observation.occurred_at) || typeof observation.phase !== 'string' || !Object.hasOwn(phases, observation.phase) || typeof observation.reference !== 'string' || observation.reference.length > 160) return fail();
        if (observation.reason_code !== null && (typeof observation.reason_code !== 'string' || !/^[a-z0-9_-]{1,80}$/.test(observation.reason_code))) return fail();
        if (observation.qualified !== null && typeof observation.qualified !== 'boolean') return fail();
        if (observation.publication !== null && !['public','not_public','unknown'].includes(String(observation.publication))) return fail();
        if (observation.readback_result !== null && !['found_matching','found_conflict','missing','unavailable'].includes(String(observation.readback_result))) return fail();
        identities.add(observation.id);
      }
    }
  }
  return raw as unknown as Snapshot;
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
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Your session is unavailable. Reload this page to sign in.');
      const next = parseSnapshot(await readBoundedJSON(response));
      if (current.current === controller) { setData(next);setUpdated(Date.now()); }
    } catch (cause) {
      if (current.current === controller) setError(cause instanceof Error && cause.name !== 'AbortError' ? cause.message : 'The request timed out. Retry when the connection is available.');
    } finally {
      clearTimeout(timer);
      if (current.current === controller) setLoading(false);
    }
  }
  useEffect(() => { document.title = 'Paperclip and OpenClaw results'; void refresh(); return () => current.current?.abort(); }, []);
  const stale = data && Date.now() - Date.parse(data.observed_through) > 3600000;
  const rows = data?.clients.map((client) => ({
    key: `${client.scope.application}/${client.scope.client}`, client: client.scope.client,
    sources: value(client.paperclip.source_offers), qualified: value(client.openclaw.qualified),
    accepted: value(client.openclaw.coverage === 'not_measured' ? null : client.openclaw.accepted_operations), confirmed: value(client.openclaw.coverage === 'not_measured' ? null : client.openclaw.destination_confirmed), published: value(client.openclaw.coverage === 'not_measured' ? null : client.openclaw.public_listings),
    waiting: value(client.exchange.unprocessed), feedback: value(client.exchange.events_waiting), uncertain: value(client.openclaw.uncertain_evaluations),
    observed: date(client.openclaw.observed_through), action: client.next_action || (client.openclaw.coverage === 'not_measured' ? 'Awaiting verified processing evidence' : 'No action recorded'),
  })) || [];
  return <Container size="xl" py="xl"><Stack gap="xl">
    <Anchor href="#results">Skip to results</Anchor>
    <Box component="header"><Stack gap="sm"><PageTitle>Paperclip and OpenClaw results</PageTitle><BodyText>Follow source research, queued work and verified results for every enrolled client.</BodyText><Anchor href="/factory/">Company overview</Anchor></Stack></Box>
    <Box component="main" id="results" tabIndex={-1} aria-busy={loading}>
      <Stack gap="lg">
        <Group justify="space-between"><SectionTitle>Delivery overview</SectionTitle><SemanticButton action="refresh" aria-label="Refresh results" onClick={() => { if (!loading) void refresh(); }} aria-busy={loading} aria-disabled={loading} /></Group>
        <Box role="status" aria-live="polite" aria-atomic="true"><BodyText>{loading ? 'Loading results…' : error ? 'Results could not be refreshed.' : updated ? 'Results updated.' : 'Results have not been loaded.'}</BodyText></Box>
        {error && <Box role="alert"><StateBlock variant="error" title="Results unavailable" /><BodyText>{error}</BodyText></Box>}
        {data && <BodyText>Snapshot {date(data.as_of)} Budapest. Observations were received during the last 24 hours. {data.coverage === 'partial' ? 'Coverage is partial; unmeasured values are shown explicitly.' : 'Coverage is complete.'} {stale ? 'This snapshot is stale.' : ''} Shared outcomes are counted once. Verified public listings describe observations during this period.</BodyText>}
        {stale && <StateBlock variant="empty" title="Older results" />}
        {loading && !data ? <StateBlock variant="loading" title="Loading results" /> : <SimpleDataTable rows={rows} getRowKey={(row) => row.key} emptyTitle="No enrolled client results" emptyDescription="" columns={[
          {key:'client',header:'Client'},{key:'sources',header:'Paperclip sources'},{key:'qualified',header:'Qualified'},
          {key:'accepted',header:'Accepted operations'},{key:'confirmed',header:'Verified operations'},{key:'published',header:'Public listings'},
          {key:'waiting',header:'Waiting'},{key:'feedback',header:'Feedback waiting'},{key:'uncertain',header:'Uncertain'},{key:'observed',header:'Processing observed through'},{key:'action',header:'Next action'},
        ]} />}
        {data && <BodyText>Delivery history shows up to 20 observations per client during the last 24 hours. A missing step is awaiting evidence.</BodyText>}
        {data?.clients.map(client => <Box component="section" key={`${client.scope.application}/${client.scope.client}`}><Stack gap="sm"><SectionTitle>{client.scope.client} delivery history</SectionTitle><SimpleDataTable emptyDescription="" emptyTitle="Waiting for delivery evidence" rows={(client.timeline || []).map(item => ({ id:item.id, at:date(item.occurred_at), system:item.phase==='source_offered'?'Paperclip':item.phase==='feedback_waiting'?'Exchange':'OpenClaw', phase:item.qualified===true&&item.phase==='checked'?'Candidate qualified':phases[item.phase], reason:item.reason_code?.replaceAll('_',' ').replaceAll('-',' ') || 'Not recorded', readback:item.readback_result?.replaceAll('_',' ') || 'Not checked', publication:item.publication==='public'?'Verified public':item.publication==='not_public'?'Verified not public':'Not measured', reference:item.reference }))} getRowKey={row=>row.id} columns={[{key:'at',header:'Observed'},{key:'system',header:'System'},{key:'phase',header:'Stage'},{key:'reason',header:'Reason'},{key:'readback',header:'Readback'},{key:'publication',header:'Publication'},{key:'reference',header:'Reference'}]} /></Stack></Box>)}
        <BodyText>Accepted cards and private leads are separate from public listings. A received packet is not a qualified candidate. Unavailable measurements do not mean zero results.</BodyText>
      </Stack>
    </Box>
  </Stack></Container>;
}
