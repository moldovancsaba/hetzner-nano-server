export async function readBoundedJSON(response: Response, maxBytes = 262144): Promise<unknown> {
  if (!response.body) throw new Error('The response contained no results.');
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) { await reader.cancel(); throw new Error('The results exceeded the display limit.'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
}

export function object(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
export function text(value: unknown): string {
  if (typeof value === 'string') return value.slice(0, 1000);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return 'Not measured';
}
export function metric(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? String(value) : 'Not measured';
}
export function time(value: unknown): string {
  const parsed = typeof value === 'number' ? value * 1000 : typeof value === 'string' ? Date.parse(value) : NaN;
  const date = new Date(parsed);
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Budapest' }).format(date) : 'Not measured';
}
export function list(value: unknown, max: number): Record<string, unknown>[] {
  if (!Array.isArray(value) || value.length > max) throw new Error('The result format is not supported.');
  return value.map(item => { const result = object(item); if (Object.keys(result).length === 0) throw new Error('The result format is not supported.'); return result; });
}
export function internalLink(value: unknown): string | null {
  return typeof value === 'string' && /^\/NAR\/[a-zA-Z0-9/_-]+$/.test(value) && value.length < 250 ? value : null;
}
