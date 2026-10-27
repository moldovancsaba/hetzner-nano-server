/** Server-side example only; does not change Camera's approval state. */
import 'server-only';
import { randomUUID } from 'node:crypto';

const baseUrl = process.env.CAMERA_MODERATION_BASE_URL ?? 'https://chatbotapi.haho.ai/v1/moderation';

export async function submitModeration(image: Buffer, requestId = randomUUID()) {
  const key = process.env.CAMERA_MODERATION_API_KEY;
  if (!key) throw new Error('Moderation is not configured; human review remains pending');
  if (!image.length || image.length > 4 * 1024 * 1024) throw new Error('Resize image before submission');
  const response = await fetch(`${baseUrl}/jobs`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json', 'Idempotency-Key': requestId },
    body: JSON.stringify({ image_base64: image.toString('base64') }),
    cache: 'no-store',
    signal: AbortSignal.timeout(20_000),
  });
  if (!response.ok) throw new Error(`Moderation unavailable (${response.status}); keep review pending`);
  const job = await response.json();
  if (typeof job.id !== 'string') throw new Error('Invalid moderation job response');
  return job.id as string;
}

export async function readModeration(jobId: string) {
  const key = process.env.CAMERA_MODERATION_API_KEY;
  if (!key) throw new Error('Moderation is not configured');
  const response = await fetch(`${baseUrl}/jobs/${encodeURIComponent(jobId)}`, {
    headers: { Authorization: `Bearer ${key}` }, cache: 'no-store', signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new Error(`Moderation unavailable (${response.status}); keep review pending`);
  // Validate camera-moderation.v1 against the documented schema before storing/displaying.
  return response.json();
}
