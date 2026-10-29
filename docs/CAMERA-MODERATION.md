# Camera moderation API: human review signals

## Camera’s twelve rejection reasons

Human approval always remains in place. See [reason-by-reason coverage and complementary model testing](CAMERA-REJECTION-COVERAGE.md). The existing API exposes nine signals that map partially to six Camera reasons; the remaining reasons must stay explicitly not evaluated. Specialist experiments do not automatically add API-selectable models or a twelve-reason endpoint.

## Retention update

The active shared gateway retains terminal results in RAM for at most five minutes, with periodic expiry. Call DELETE /v1/jobs/{id} or DELETE /v1/moderation/jobs/{id} after consumption. This supersedes the retired standalone worker’s 15-minute retention. No live image or conversation is captured for training. See [retention policy](DATA-RETENTION.md).

## Model selection update

Use `model: auto` or omit model for the best currently tested moderation model. A selectable tested override can be supplied as `model` beside `image_base64` on the existing submit route. Camera can now call `/v1/models` and `/v1/job-types` for installed alternatives. General image recognition uses a separate ranking/default. See [ranked model policy](MODEL-POLICY.md) for the authoritative selection contract.

## Shared queue update

This API now runs through the [shared job router](JOB-ROUTER.md), together with ClassScout text and Pandora. Existing moderation submit/poll endpoints and the Camera key remain valid. The old standalone worker is stopped/disabled. The router supports general image recognition too, via `POST /v1/jobs` with task `image_recognition`. Queue limits, health shape, runtime credential location, lifecycle fields and switching behavior in the router guide supersede the original deployment details below.

## Purpose and status

An experimental screening service whose current ranked default is **Qwen3.5 0.8B** (explicit `think=false`), deployed on the existing 4 GB Hetzner server. It highlights possible concerns for Camera's existing human photo-vetting workflow. It never approves, rejects, publishes, emails, or changes Camera records. No Camera application code or Vercel variables were changed by this deployment.

The [broader independent benchmark](../benchmarks/vision-evaluation/REPORT.md) compares five models on 41 images and found missed violations and false alarms. Qwen ranks narrowly first on equal-category macro F2 (0.694), followed by MiniCPM (0.690); these close scores do not demonstrate general superiority. Qwen returned 41/41 valid responses with a median near 38 seconds; MiniCPM was faster near 22 seconds and remains an explicit alternative. Per-category positive counts are only two to five, so uncertainty is wide. This is public research evaluation, not representative Camera production accuracy. Both leading models missed both controlled English hate-word positives and detected only one of three violence positives. Those categories particularly need independent review. Correct JSON is not reliable classification. `no_flags_detected` must not mean safe/approved. Review remains required for every completed result, including all-negative results. No numeric confidence is provided: none has been calibrated.

## Connection and credentials

Base URL: `https://chatbotapi.haho.ai/v1/moderation`

Server-only environment:

```dotenv
CAMERA_MODERATION_BASE_URL=https://chatbotapi.haho.ai/v1/moderation
CAMERA_MODERATION_API_KEY=<dedicated-camera-key>
```

The key is in the canonical root-only server `/opt/narimato-ai/api-keys.json` under `camera`, the owner's ignored local `private/api-keys.json`, and `private/camera-moderation.env`. Authorized agents can copy it directly into Camera's ignored server environment. Do not put it in source, browser JavaScript, `NEXT_PUBLIC_*`, image metadata, logs or this public repository. It is separate from Habigoal/ClassScout keys and grants Camera moderation, recognition, task/model discovery and queue routes; it does not grant text inference or model-management access. Habigoal/ClassScout bearer keys cannot access moderation. `private/` is not included in Git clones.

The active gateway reads `/etc/narimato-gateway.env` (Camera field `GATEWAY_CAMERA_KEY`). The retired standalone worker used `/etc/narimato-moderation.env`. Rotation: replace only the Camera key in the canonical JSON, securely refresh that env file/local snapshots and Camera's authorized server environments, then drain/restart `narimato-gateway`. Old in-flight job IDs are lost by restart. Caddy forwards the bearer header to this service and contains no Camera key.

## Submit a still image

`POST /jobs` with `Authorization: Bearer <camera key>`, `Content-Type: application/json`, optional `Idempotency-Key` (ASCII, at most 128 characters):

```json
{"image_base64":"<standard base64 image bytes, without data: prefix>"}
```

The image property and optional `model` are accepted; use `model: "auto"` for the ranked default or a selectable exact model ID from `/v1/models`. No URL fetching, personal identifiers, event names, email addresses, EXIF fields or arbitrary prompts. Read private image bytes inside Camera's trusted server code; do not make pending photos public for this API. Preserve Camera's source permissions, revision and deletion/consent rules.

Limits: JPEG/PNG/WebP still images only; 4 MiB decoded file, 16 megapixels, 6 MiB JSON request. Animated images and movies are rejected. Input is EXIF-oriented, resized to maximum edge 640, flattened onto white if transparent and re-encoded as JPEG without metadata. Client-side/server-side preparation to 640 pixels reduces transfer time, but retain an original source revision and use original details for human review. Small details may disappear at this size.

Response **202 Accepted**:

```json
{
  "id": "opaque-job-id",
  "status_url": "/v1/moderation/jobs/opaque-job-id",
  "review_required": true
}
```

`Location` also identifies the job. Save the returned ID with the Camera photo's current source revision. A repeated idempotency key with identical image bytes returns the same job during its lifetime; changed bytes with the same key return 409. Keys expire with jobs and are not durable across service restart. Use a new key for a deliberately new analysis generation, and never embed user personal data in it.

## Poll for results

`GET /jobs/{id}` with the same bearer key. Poll every 2–5 seconds from a background worker; do not hold a browser or Vercel request open waiting for model inference. Responses are HTTP 200 for known jobs, with status `queued`, `running`, `completed` or `failed`. A failed job is still a successfully retrieved resource, not a successful analysis.

A completed response contains:

```json
{
  "id": "opaque-job-id",
  "status": "completed",
  "created_at": 1793090000.0,
  "started_at": 1793090001.0,
  "finished_at": 1793090008.0,
  "image_sha256": "original-byte-hash",
  "normalized_sha256": "processed-byte-hash",
  "result": {
    "schema_version": "camera-moderation.v1",
    "model": "qwen3.5:0.8b",
    "review_required": true,
    "automated_decision": "none",
    "signal": "flagged",
    "flags": ["weapons"],
    "categories": {
      "nudity": "not_detected",
      "sexualContent": "uncertain",
      "middleFinger": "not_detected",
      "hateSymbols": "not_detected",
      "hateWords": "not_detected",
      "alcohol": "not_detected",
      "drugs": "not_detected",
      "violence": "not_detected",
      "weapons": "detected"
    },
    "evidence": "Brief model-generated visible-evidence description.",
    "limitations": "Experimental screening; missed content and false alarms are known. No flags is not approval.",
    "timing": {"model_load_seconds": 1.3, "inference_seconds": 7.3}
  }
}
```

The example is illustrative, not a measured prediction. Category values are `detected`, `not_detected`, or `uncertain`. `signal` is `flagged` if any category is detected, otherwise `uncertain` if any category is uncertain, otherwise `no_flags_detected`. The `flags` array contains only detected categories. Times outside `result.timing` are Unix seconds. All category decisions and evidence are untrusted model output; display evidence as text, not HTML or instructions.

Categories follow the benchmark's documented review rubric: nudity; explicit sexual/pornographic content (not nudity alone); middle finger; hate symbols; English visible hate words; alcohol; drug-related content with ambiguity preserved; violence/coercive harm; real weapons. Toys/paintball markers are hard negatives under the tested rubric. Legal status and substance chemistry cannot be established from an image. Non-English text, explicit sexual acts and broad real-world scenarios are not certified by this test. There is no catch-all `other` category in v1.

Failed job shape:

```json
{"id":"opaque-job-id","status":"failed","error":{"code":"analysis_unavailable","message":"Analysis failed or timed out. Keep human review pending; retry later."},"review_required":true}
```

Additional lifecycle/hash fields may be present. Invalid, truncated, absent or failed model output never produces a completed all-negative result.

## Errors, retries and retention

| HTTP | Meaning | Camera action |
| --- | --- | --- |
| 400 | Invalid image/request or unsupported image dimensions/format | Fix input; keep review pending |
| 401 | Missing/wrong Camera key | Fix server configuration; do not bypass vetting |
| 404 | Unknown/expired job or lost on service restart | Resubmit eligible current photo if still needed |
| 409 | Same idempotency key used for different bytes | Use the correct source revision/new analysis key |
| 413 | Request size exceeds limit | Resize/compress input |
| 415 | Wrong content type | Send JSON |
| 429 | Queue or retained-result capacity reached | Honor Retry-After: 10; exponential backoff with jitter |
| 5xx / network / TLS / timeout | Service unavailable | Keep manual review available and retry later |

One shared active worker, eight waiting jobs globally, at most four queued/running per service and 64 retained job records. Results expire five minutes after completion/failure with periodic expiry. Jobs/results exist only in memory and disappear at restart. Images are kept only in the bounded in-memory queue/worker, never written to disk by this service. Input bytes are discarded after inference. Minimal metadata, hashes and evidence remain until expiry/restart; Camera chooses its own authorized retention and must not keep results after source deletion/withdrawal. Model/service logs do not intentionally contain image bytes or results. Infrastructure administrators still control the host; this is not an encrypted enclave.

There is no durable queue or webhook. Authenticated `DELETE /jobs/{id}` acknowledges/removes a terminal result or cancels queued work; active inference returns 409. If the source loses eligibility while a job runs, Camera must discard its result and perform its own cleanup. Never retry a deleted/ineligible source. A job expiring is not proof that Camera has deleted its copy.

## Camera integration workflow

1. Keep existing vetting/authorization as the source of truth. Schedule an optional screening job after private source bytes are available.
2. Submit the unframed current photo, without publicizing its Blob URL. Persist job ID, input hash and source revision in an appropriate analysis field/collection only after Camera's contract review.
3. Poll in a durable/background workflow; validate schema version, statuses and all nine category values. Apply a result only to the matching current source revision.
4. In the existing reviewer interface show “Possible concerns”, category signals and evidence. A failed/expired job shows “Analysis unavailable”; all-negative shows “No concerns detected by the screening model”, never “Safe”.
5. Human reviewers retain approve/reject controls, original image access and audit trail. This API does not replace or call Fanmass and must not mark Fanmass's required analysis modules complete.
6. Retry transient failures with bounded backoff. Keep queues bounded per event and prioritize human workflow availability over screening completion.

[Server-side TypeScript example](../examples/camera-moderation.ts) provides submit/read functions only. It is not installed in Camera. Poll on later worker ticks, validate responses and handle all failure states before integration. No new browser UI is needed to use the API.

## Local operator test

```sh
python3 scripts/camera_moderation.py /absolute/path/to/test-image.jpg
```

The helper reads the dedicated key from the ignored local key file or `CAMERA_MODERATION_API_KEY`. It prints a result, never the key. Use non-sensitive test images in shared terminals. Do not share raw output containing private-photo evidence.

## Original standalone deployment (superseded)

The following records the initial implementation for rollback. **Use [shared-router operations](JOB-ROUTER.md#operations-and-changing-assignments) for the active deployment; do not start the retired worker alongside it.**

### Original operations and model switching

Service: `narimato-moderation`; code `/opt/narimato-moderation`; loopback `127.0.0.1:8089`; native inference loopback `127.0.0.1:11434`. Caddy exposes only the dedicated routes. Unit memory cap 384 MiB and CPUQuota 50%; Ollama remains capped at 2800 MiB/2 CPUs. One model and one generation at a time in Ollama; the moderation service processes one image at a time. Its HTTP connections are bounded to eight, with a single upload-normalization slot; simultaneous uploads can receive 429 before queue admission.

The 450M model is installed persistently on disk. Each job uses context 2048, batch 32, output 256, temperature zero, and `keep_alive: 1m`. Ollama switches the resident model when chat/image workloads differ; this service does not delete, forcibly unload or rewrite the chat model. Idle vision unloads after its retention period; the next chat request reloads Qwen3 as needed. Model switching adds delay. The earlier median ~7.3 seconds was a benchmark, not an API latency guarantee. Shared chat traffic is not coordinated by a global application scheduler; do not promise uninterrupted low-latency chat or high-throughput screening. A timed-out inference may continue upstream; the worker applies a 30-second recovery pause and keeps review pending. Native Ollama queue limits still apply.

Health: authenticated `GET /health` checks the moderation HTTP worker, not model accuracy or upstream readiness. Verify a real job separately after deployment/model updates.

These commands apply only to a deliberate rollback of the retired worker. Checked 2026-10-29: the unit is disabled and not loaded on the host, so they report it as missing. For the active service use `systemctl status narimato-gateway`.

```sh
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'systemctl status narimato-moderation --no-pager'
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'journalctl -u narimato-moderation -n 40 --no-pager'
```

Deploy source/unit, install distribution `python3-pil`, pull the exact model, validate configuration, and run `moderation/deploy.py` on the server only. The deployment helper generates/preserves Camera's key, creates a root-only env file, backs up/validates Caddy before reload, and enables the unit. Inspect code and server state first. Restart to load source/key changes. Do not run it from a laptop expecting local paths to provision the server. Rollback: remove the moderation Caddy handle using the root-only pre-deployment backup after checking for intervening changes, validate/reload Caddy, and stop/disable `narimato-moderation`; preserve other routes/keys and leave model weights unless disk removal is intentionally requested.
