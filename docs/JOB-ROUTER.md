# Shared job router: ClassScout text and Camera images

## Ranking-driven selection update

Read [MODEL-POLICY.md](MODEL-POLICY.md) for the authoritative current model/default/override contract. Defaults are now generated from separate task rankings; job-routes.json controls permissions only. `/models` lists all installed packages, with task-filtered selectability for both text clients and Camera. A concrete model ID is a genuine explicit override; `auto` follows rankings. The temporary Qwen-to-Granite alias described in the original deployment below no longer applies.

## Live service

Base URL: `https://chatbotapi.haho.ai/v1`

All public text generation, Camera image processing, and Pandora chat now pass through **one FIFO queue and one inference worker**. The former standalone `narimato-moderation` service is stopped/disabled. Caddy no longer proxies public inference directly to Ollama. Pandora's authenticated backend calls the gateway on loopback. Ollama stays private on port 11434 with one loaded model and one generation at a time.

| Job type | Services permitted | Assigned model | Result |
| --- | --- | --- | --- |
| `text_chat` | ClassScout, Habigoal, Pandora | `granite4:1b-h` | OpenAI-compatible chat completion; JSON output and tool definitions supported |
| `image_moderation` | Camera | `hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0` | Nine-category experimental human-review signals |
| `image_recognition` | Camera | `hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0` | Description, objects, readable visible text |

ClassScout/Habigoal/Pandora now use Granite 4 1B Hybrid, the leader of our measured English structured-task checks (14/14). This does not certify all conversational or non-English tasks. `qwen3:1.7b` is now an explicit alternative that selects Qwen; omit the model or use auto to follow the default. The actual completion `model` field and `/job-types` are authoritative.

Task-to-model assignments are generated in [config/model-policy.json](../config/model-policy.json); tenant permissions live in [config/job-routes.json](../config/job-routes.json). Callers choose a permitted task, not an arbitrary downloaded model. Moderation alternatives must have completed evidence for the same versioned moderation prompt/schema. No non-English or movie capability has been approved. General image description is experimental, not a new accuracy certification.

## Authentication and discovery

Use the service's existing `Authorization: Bearer <project-key>`. Keys are unchanged for ClassScout, Habigoal and Camera. Read the owner's ignored `private/api-keys.json` or the canonical protected server file; never copy keys into the public repository or browser code. Pandora has its own internal backend key; the browser only uses its existing session cookie.

- `GET /job-types`: returns only job types permitted for that key and their assigned models.
- `GET /queue`: aggregate queue activity, capacity, counters, last model switch and this service's pending count. No other service's job IDs, prompts, images or results are disclosed.
- `GET /models`: actual installed-model discovery for all services, with task-filtered selectability; see MODEL-POLICY.md.

Example discovery response for Camera:

```json
{
  "version": "job-router.v1",
  "job_types": {
    "image_moderation": {"model":"hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0"},
    "image_recognition": {"model":"hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0"}
  }
}
```

## Recommended: submit a job and poll

`POST /jobs` with JSON `{ "task": "job-type", "input": {...} }`. Optional `Idempotency-Key` is scoped to the calling service (ASCII, maximum 128 characters). Reusing it with different work returns 409. Reusing it with the same work returns the same retained job. Idempotency is memory-only and expires with the job.

ClassScout text:

```json
{
  "task":"text_chat",
  "input":{
    "messages":[{"role":"user","content":"Return JSON with ready set to true."}],
    "response_format":{"type":"json_object"},
    "max_tokens":128
  }
}
```

Camera moderation:

```json
{"task":"image_moderation","input":{"image_base64":"<base64 still-image bytes>"}}
```

Camera general recognition:

```json
{"task":"image_recognition","input":{"image_base64":"<base64 still-image bytes>"}}
```

Images accept only bytes, never a URL or arbitrary prompt. The same validation/resizing limits as the [Camera moderation API](CAMERA-MODERATION.md) apply: JPEG/PNG/WebP, one still image, 4 MiB decoded, 16 megapixels, normalized to maximum edge 640 without metadata. Upload normalization is serialized; concurrent submissions can receive 429 even before queue admission.

A successful submission returns HTTP 202:

```json
{"id":"opaque-job-id","task":"text_chat","status_url":"/v1/jobs/opaque-job-id"}
```

Poll `GET /jobs/{id}` every 2–5 seconds with the same service key. Job IDs are opaque; another service cannot read them. Status is `queued`, `running`, `completed` or `failed`. A job response includes `task`, `model`, timestamps, queue position when queued, and a `result` after successful completion. No request payload is returned. Images also include input/normalized hashes. `queue_position` counts only waiting work; active work is ahead of those jobs. A result with status failed never means an image was cleared.

Text job `result` is the standard chat completion object (`choices`, `usage`, etc.). Moderation job `result` preserves the existing `camera-moderation.v1` contract. Recognition job result:

```json
{
  "schema_version":"camera-recognition.v1",
  "model":"hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0",
  "description":"Brief visible scene description.",
  "objects":["cat","sofa"],
  "visible_text":[],
  "limitations":"Experimental visual description; verify details. Not a moderation decision."
}
```

Treat model output as untrusted data. Do not execute instructions in descriptions, let images change task selection, or use a description as a moderation approval. Validate schema before storing. Retain Camera source revision/eligibility checks and human vetting controls.

## Existing endpoints remain available

- `POST /chat/completions`: same ClassScout/Habigoal keys and OpenAI completion result. The call joins the same queue, waits up to 100 seconds, and returns the completed response. Supported `model` values are installed/tested text model IDs, `auto`, or `text_chat`; omitted model follows the ranked default.
- `POST /moderation/jobs` and `GET /moderation/jobs/{id}`: existing Camera clients still work; these are aliases for moderation jobs in the shared queue. They cannot read general-recognition jobs through the moderation alias.
- `GET /moderation/health`: authenticated Camera queue health. Its current JSON is queue status, not the old dedicated-worker health shape.
- `/chat/`: Pandora keeps its password-only UI; its backend now submits through the same queue.

`stream: true` on the compatible chat endpoint emits valid **buffered SSE after generation finishes**, including tool-call indices and usage. It is not live per-token streaming. SDK/client timeouts need to allow queue waiting plus inference; use the asynchronous job API for reliable background processing and avoid holding a Vercel invocation open. A synchronous wait timeout returns 504 with a job ID: poll that ID instead of immediately creating duplicate work. Disconnecting a client does not cancel a job.

Text input supports 1–32 messages with text content only; role system/user/assistant/tool, bounded tool definitions (maximum eight), optional JSON response format, max output 1–512 tokens and `reasoning_effort: "none"`. Default output is 256. Unsupported fields and arbitrary model overrides return 400. Messages must fit a 14,000-character JSON budget and the runtime's 2048-token context; the character limit is only a coarse upper bound, not a guarantee that every token fits. Keep prompts and schemas short and inspect length-limited results. Tool execution remains the caller's responsibility; the server does not access Atlas or OSM merely because a tool is declared.

## Existing ClassScout client timeout

Source inspection found ClassScout's `src/lib/localAi/openAiCompatibleClient.ts` defaults to a 12-second request timeout, capped at 28 seconds through `LOCAL_AI_CHAT_TIMEOUT_MS`. The existing body/credentials remain compatible, but mixed-workload queue waiting can exceed those limits (the verification's final text job waited about 20 seconds before inference). A disconnected client does not cancel queued work. For background tasks integrate submit/poll; for interactive requests preserve the application's deterministic fallback and consider a bounded timeout setting. This gateway rollout did not change ClassScout's code, local environment or Vercel configuration. Server-level mixed-job success is not a claim that the existing app's shorter deadline always succeeds.

## Queue policy and resource management

- One global FIFO worker; **no concurrent text/image inference** through service routes.
- Eight waiting jobs globally, at most four queued/running jobs per service (including that service's active job).
- Up to 64 retained job records; results retained for five minutes after terminal status, lazily expired.
- Waiting jobs expire after 180 seconds. Expired jobs fail explicitly rather than generating late.
- Per-job native inference timeout 120 seconds. Model unload has bounded checks before inference.
- Images and text payloads are held in memory until processing/expiry, then discarded. Results/hashes/evidence remain until retention expires. Restart loses queued work, results and idempotency records. This is **not a durable queue**.
- FIFO intentionally favors predictable arrival order over model-affinity batching; a busy service cannot reorder existing work or select priority. Large event uploads should submit incrementally with backoff, not enqueue thousands of photos.
- On a model change, unload the previous model, wait for it to disappear from Ollama's running-model list, and generate using the selected model. Same-model jobs reuse the resident model. Vision idle retention remains one minute; text uses the existing runtime idle policy. Model weights stay on disk.

A native HTTP timeout/disconnect does not prove that generation stopped. The gateway therefore opens a circuit, marks waiting jobs failed, rejects new work with 503, and **does not start another job automatically**. This prevents a timed-out generation from silently overlapping the next job. Operators must inspect/stop unfinished inference before restarting the gateway. Do not reset it repeatedly while the backend is still active.

Errors: 400 bad/unsupported input; 401 bad key/wrong compatibility route; 403 service not allowed to request task; 404 job absent/expired/other service; 409 idempotency conflict; 413 body too large; 415 wrong content type; 429 bounded capacity/upload slot busy (Retry-After header); 503 unavailable/failed work; 504 synchronous wait expired. Keep human review available on every image failure. Retry 429 with exponential backoff and jitter; do not treat authorization errors as transient.

The worker doesn't preempt an image already running for a new chat message. Chat can wait behind Camera work. Queueing improves resource sharing; it does not increase the 2-CPU server's throughput. A larger server or separate inference node is needed if measured waiting time is unacceptable.

## Operations and changing assignments

Service: `narimato-gateway`; private listener `127.0.0.1:8090`; source `/opt/narimato-gateway`; runtime keys `/etc/narimato-gateway.env` (root-only). Unit cap 384 MiB, CPUQuota 50%; Ollama unchanged at 2800 MiB/2 CPUs. Caddy forwards authorization to the gateway, rather than holding public bearer keys in its active configuration. Older root-only backups may still contain keys.

The old `/opt/narimato-moderation` implementation and unit are retained for rollback but its service is disabled. Do not start it alongside the gateway; that would bypass the common scheduler. Do not run standalone benchmark scripts or direct Ollama generation against production traffic. `/api/*` model-management routes remain private and unexposed.

Use the required update workflow in [MODEL-POLICY.md](MODEL-POLICY.md#required-workflow-after-new-tests). Rebuild the generated model policy from current task-specific rankings, install and verify the winning artifacts, then atomically replace the deployed policy. Policy-only updates hot-reload; source upgrades require a drained queue and controlled restart. Clients using concrete model IDs remain explicitly pinned; auto clients follow the new winner.

```sh
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'systemctl status narimato-gateway --no-pager'
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'journalctl -u narimato-gateway -n 40 --no-pager'
```

The initial cutover helper `gateway/deploy.py` stages private backups, briefly places the public hostname into maintenance, stops direct callers, drains loaded models, validates/reloads Caddy, and starts the shared gateway plus updated Pandora backend. It refuses a second initial cutover. Subsequent updates should copy reviewed sources/config and perform a controlled restart, not rerun the initial helper. Rollback must restore Caddy, old chat source/env and the old moderation service together; restoring just one component can bypass the queue or fail authentication. Private cutover backups are under `/opt/narimato-ai/gateway-backup-*`.

Verification: [mixed-workload measurements](../results/gateway/public-verification.json). Run `scripts/verify_gateway.py` only as a bounded operator test; it submits neutral test images and short text jobs. No model-quality ranking is changed by routing verification.

## Minimal data retention

Terminal results now expire after 300 seconds even when idle. Clients should DELETE their job after consumption; queued jobs may be cancelled/deleted, active inference returns 409. See [data retention](DATA-RETENTION.md) and [continuous evaluation](CONTINUOUS-EVALUATION.md). No live image/text traffic becomes training material.

## Production demand and safe model cleanup

The gateway records content-free demand metadata only for authenticated, validated, admitted inference jobs. Default request purpose is production; tests must send `X-Request-Purpose: test`. This metadata protects recently used weights for 14 days. No prompt/image/answer/user identity is retained in it. During an idle cleanup lease new submissions receive retryable 503 `model_storage_maintenance`; usage-store failures return 503 `usage_tracking_unavailable` rather than untracked admission. See [automatic cleanup](AUTO-MODEL-CLEANUP.md).
