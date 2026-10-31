# Shared job router: ClassScout text and Camera images

## Ranking-driven selection update

Read [MODEL-POLICY.md](MODEL-POLICY.md) for the authoritative current model/default/override contract. Defaults are now generated from separate task rankings; job-routes.json controls permissions only. `/models` lists all installed packages, with task-filtered selectability for both text clients and Camera. A concrete model ID is a genuine explicit override; `auto` follows rankings. The temporary Qwen-to-Granite alias described in the original deployment below no longer applies.

## Live service

Base URL: `https://chatbotapi.haho.ai/v1`

All public text generation, Camera image processing, and Pandora chat now pass through **one FIFO queue and one inference worker**. The former standalone `narimato-moderation` service is stopped/disabled. Caddy no longer proxies public inference directly to Ollama. Pandora's authenticated backend calls the gateway on loopback. Ollama stays private on port 11434 with one loaded model and one generation at a time.

| Job type | Services permitted | Assigned model | Result |
| --- | --- | --- | --- |
| `text_chat` | ClassScout, Habigoal, Pandora, Paperclip | `granite4:1b-h` | OpenAI-compatible chat completion; JSON output and tool definitions supported |
| `text_chat_hu` | ClassScout, Habigoal, Pandora, Paperclip | Qwen3-4B-Instruct-2507 Q3_K_M (unsloth GGUF build; exact ID in `/job-types`) | Experimental short Hungarian chat completion; see [HUNGARIAN.md](HUNGARIAN.md) |
| `image_moderation` | Camera | `qwen3.5:0.8b` | Nine-category experimental human-review signals |
| `image_recognition` | Camera | `minicpm-v4.6:q5_K_M` | Description, objects, readable visible text |

Permissions come from `config/job-routes.json`; there are no other combinations. Camera cannot submit text jobs, and the four text services cannot submit image jobs. Each key has its own limit on queued plus running jobs (see [Queue policy](#queue-policy-and-resource-management)).

ClassScout/Habigoal/Pandora/Paperclip now use Granite 4 1B Hybrid, the leader of our measured English structured-task checks (14/14). This does not certify all conversational or non-English tasks. `qwen3:1.7b` is now an explicit alternative that selects Qwen; omit the model or use auto to follow the default. The actual completion `model` field and `/job-types` are authoritative.

Task-to-model assignments are generated in [config/model-policy.json](../config/model-policy.json); tenant permissions live in [config/job-routes.json](../config/job-routes.json). Callers choose a permitted task, not an arbitrary downloaded model. Moderation alternatives must have completed evidence for the same versioned moderation prompt/schema. No non-English or movie capability has been approved. General image description is experimental, not a new accuracy certification.

## Authentication and discovery

Use the service's existing `Authorization: Bearer <project-key>`. Keys are unchanged for ClassScout, Habigoal and Camera. Read the owner's ignored `private/api-keys.json` or the canonical protected server file; never copy keys into the public repository or browser code. Pandora has its own internal backend key; the browser only uses its existing session cookie.

- `GET /job-types`: returns only job types permitted for that key, each with its ranked default, whether that default is experimental, and the installed models selectable for it.
- `GET /queue`: aggregate queue activity, capacity, counters, last model switch and this service's pending count. No other service's job IDs, prompts, images or results are disclosed.
- `GET /models`: actual installed-model discovery for all services, with task-filtered selectability; see MODEL-POLICY.md.
- `GET /usage?hours=N`: this key's own operational report, up to 168 hours; see [OBSERVABILITY.md](OBSERVABILITY.md).

Example discovery response for Camera (`available_models` lists whatever is installed and selectable at that moment, so it varies):

```json
{
  "version": "job-router.v2",
  "policy_id": "<sha256 of the deployed model-policy.json>",
  "job_types": {
    "image_moderation": {
      "model": "qwen3.5:0.8b",
      "selection": "ranking_default",
      "experimental": false,
      "available_models": ["qwen3.5:0.8b", "hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0"]
    },
    "image_recognition": {
      "model": "minicpm-v4.6:q5_K_M",
      "selection": "ranking_default",
      "experimental": false,
      "available_models": ["minicpm-v4.6:q5_K_M", "hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0"]
    }
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
  "model":"minicpm-v4.6:q5_K_M",
  "description":"Brief visible scene description.",
  "objects":["cat","sofa"],
  "visible_text":[],
  "limitations":"Experimental visual description; verify details. Not a moderation decision."
}
```

Treat model output as untrusted data. Do not execute instructions in descriptions, let images change task selection, or use a description as a moderation approval. Validate schema before storing. Retain Camera source revision/eligibility checks and human vetting controls.

## Experimental Hungarian job

Use `text_chat_hu` with `model: auto` for explicit short Hungarian tests. Discover its experimental flag and profile; no model passed the Hungarian production gate. Follow [the separate API guide](HUNGARIAN.md) and [agent prompt](AGENT-PROMPT-HU.md). It shares FIFO scheduling and result deletion but has a much smaller context than English.

## Existing endpoints remain available

- `POST /chat/completions`: same ClassScout/Habigoal keys and OpenAI completion result. The call joins the same queue, waits up to 100 seconds, and returns the completed response. Supported `model` values are installed/tested text model IDs, `auto`, or `text_chat`; omitted model follows the ranked default.
- `POST /moderation/jobs` and `GET /moderation/jobs/{id}`: existing Camera clients still work; these are aliases for moderation jobs in the shared queue. They cannot read general-recognition jobs through the moderation alias.
- `GET /moderation/health`: authenticated Camera queue health. Its current JSON is queue status, not the old dedicated-worker health shape.
- `/chat/`: Pandora keeps its password-only UI; its backend now submits through the same queue.

`stream: true` on the compatible chat endpoint emits valid **buffered SSE after generation finishes**, including tool-call indices and usage. It is not live per-token streaming. SDK/client timeouts need to allow queue waiting plus inference; use the asynchronous job API for reliable background processing and avoid holding a Vercel invocation open. A synchronous wait timeout returns 504 with a job ID: poll that ID instead of immediately creating duplicate work. Disconnecting a client does not cancel a job.

Text input supports 1–32 text messages with roles system/user/assistant/tool and up to eight tool definitions. The default Granite profile now allows 8192 total tokens and output 1–1024 (default 256), with reasoning_effort none, verified token counting and conservative template/output reserves. Inputs above 4096 counted tokens require async jobs. Explicit alternative models retain their earlier tested limits. Tool execution remains the caller's responsibility; declaring a tool does not grant database or internet access. See CHATBOT-CONTEXT.md.

## Existing ClassScout client timeout

Source inspection found ClassScout's `src/lib/localAi/openAiCompatibleClient.ts` defaults to a 12-second request timeout, capped at 28 seconds through `LOCAL_AI_CHAT_TIMEOUT_MS`. The existing body/credentials remain compatible, but mixed-workload queue waiting can exceed those limits (the verification's final text job waited about 20 seconds before inference). A disconnected client does not cancel queued work. For background tasks integrate submit/poll; for interactive requests preserve the application's deterministic fallback and consider a bounded timeout setting. This gateway rollout did not change ClassScout's code, local environment or Vercel configuration. Server-level mixed-job success is not a claim that the existing app's shorter deadline always succeeds.

## Queue policy and resource management

- One global FIFO worker; **no concurrent text/image inference** through service routes.
- Eight waiting jobs globally. Each service may have at most four jobs queued plus running at once (its active job counts); Paperclip may have one. A job over either limit is refused with 429 `busy`. `GET /queue` always reports `per_service_limit: 4`, including to Paperclip; see Known limitations in [OPERATIONS.md](OPERATIONS.md).
- Up to 64 retained job records; results retained for five minutes after terminal status, lazily expired.
- Waiting jobs expire after 180 seconds. Expired jobs fail explicitly rather than generating late. The limit applies to queued jobs only; a running job is not expired by it.
- Native inference timeouts per job: 120 seconds for image moderation, image recognition, Hungarian text and text on a 2048-token profile; 900 seconds for text on the verified 8K profile that the default text route uses (`timeout_seconds` in `config/runtime-context-profiles.json`). The synchronous `/chat/completions` call stops waiting after 100 seconds and returns 504 while the job keeps running. The private watchdog raises `inference_stuck` after 300 seconds of one active job, so a legitimate long 8K job can raise it. Model unload has bounded checks before inference (up to about 10 seconds).
- Images and text payloads are held in memory until processing/expiry, then discarded. Results/hashes/evidence remain until retention expires. Restart loses queued work, results and idempotency records. This is **not a durable queue**.
- FIFO intentionally favors predictable arrival order over model-affinity batching; a busy service cannot reorder existing work or select priority. Large event uploads should submit incrementally with backoff, not enqueue thousands of photos.
- On a model change, unload the previous model, wait for it to disappear from Ollama's running-model list, and generate using the selected model. Same-model jobs reuse the resident model. Vision idle retention remains one minute; text uses the existing runtime idle policy. Model weights stay on disk.

A native HTTP timeout/disconnect does not prove that generation stopped. The gateway therefore opens a circuit, marks waiting jobs failed, rejects new work with 503, and **does not start another job automatically**. This prevents a timed-out generation from silently overlapping the next job. The circuit never closes on its own and there is no reset endpoint: only restarting `narimato-gateway` clears it, and a restart discards queued jobs, results and idempotency records. While it is open, `GET /queue` reports `status: degraded`, new work gets 503 `upstream_unavailable`, and the model cleaner cannot take a maintenance lease. Operators must inspect/stop unfinished inference before restarting the gateway. Do not restart repeatedly while the backend is still active.

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

The gateway records content-free demand metadata only for authenticated, validated, admitted inference jobs. Default request purpose is production; tests must send `X-Request-Purpose: test`. This metadata protects recently used weights for 3 days (`keep_production_request_days` in `config/model-storage-policy.json`). No prompt/image/answer/user identity is retained in it. During an idle cleanup lease new submissions receive retryable 503 `model_storage_maintenance`; usage-store failures return 503 `usage_tracking_unavailable` rather than untracked admission. See [automatic cleanup](AUTO-MODEL-CLEANUP.md).

## Paperclip 8K text tenant

Paperclip has an independent text-only key. `GET /v1/models` exposes the verified 8192-token Granite context profile only to this tenant; unverified alternate contexts are blocked. Use `POST /v1/jobs` with task `text_chat`, model `auto`, and the chat object in `input`; poll the returned job ID. Long inputs above 4096 counted tokens cannot use synchronous chat. Maximum output is 1024 tokens, with output and conservative template space reserved before admission; maximum body 256 KiB and one pending Paperclip job. Other tenants retain their previous limits. See ../paperclip/README.md and ../benchmarks/paperclip-context/README.md. Tests must still send X-Request-Purpose: test.

The 8K tenant profile now also covers default ClassScout, Habigoal and Pandora text. Pandora's UI uses async jobs and token-aware recent history. Paperclip remains at one pending job; existing other tenant queue limits are retained. Read CHATBOT-CONTEXT.md for the current limits rather than treating the earlier Paperclip-only rollout as the current full tenant policy.
