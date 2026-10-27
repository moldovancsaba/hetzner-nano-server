# Ranked defaults and client model selection

## Standing policy

**Default services always use the best eligible model in the current ranking for their job.** Future testing exists to improve those assignments. Completing a new benchmark means updating its ranking evidence, rebuilding/deploying this policy and verifying the live defaults; leaving the previous winner deployed is unfinished work.

Rankings remain separate. Current defaults:

| Job | Ranking | Default |
| --- | --- | --- |
| English text / ClassScout / Pandora | English structured-task ranking | `granite4:1b-h` |
| General Camera image recognition | General image ranking | `hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0` |
| Camera forbidden-content assistance | Moderation-specific ranking | `hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0` |

The older LFM2 vision model comes first in the general image table by its descriptive timing tie-break. That does not establish statistically superior visual quality over the tied LFM2.5 model. Moderation uses its own evidence, not general image scores: its ordering uses positive detections, known correct decisions, false positives, then latency. Per-category results remain visible, and neither tested model was approved for automatic enforcement. English structured-task results are the current text selection proxy; they do not certify broad conversation quality. Non-English and movies remain independent, unapproved workstreams.

## One machine-readable policy

- `config/ranking-sources.json` selects the current canonical ranking/result sources. Point it to the new round when adding a newer canonical ranking; do not create conflicting current rankings.
- `scripts/promote_rankings.py --write` derives **config/model-policy.json** from those sources. Despite its name, this script only builds model policy; it does not publish anything to GitHub or deploy a service.
- The generated file contains task winners, model/task ranks, benchmark metrics, tested profiles, exact tested artifact digests, source hashes and a deterministic policy ID.
- `--check` fails if that file is stale or inconsistent with its source evidence. Unit tests also enforce this.
- `config/job-routes.json` controls tenant permissions and ranking-task names; it no longer hard-codes a second set of model choices.
- The running gateway reads the deployed policy on each discovery/selection. Atomic policy replacement is effective without a restart. Each accepted job records its selected model, artifact digest, profile and policy ID; later changes do not silently retarget queued work.

Only models with completed task evidence enter selection. Installed models which failed eligibility or have no evidence for a permitted job are listed but blocked. A changed digest invalidates eligibility until the changed artifact is tested. Installed means on disk, not resident in RAM.

If the top-ranked default is missing or its digest differs, automatic requests fail explicitly with 503. **There is no silent lower-ranked fallback.** Operators must install/verify the winner as part of updating policy. An explicitly selected lower-ranked installed/tested model is allowed because that is the client's choice.

## Discover actual installed models

`GET https://chatbotapi.haho.ai/v1/models` with the service's bearer key now works for text services **and Camera**. It returns actual Ollama-installed packages, including blocked ones. Inventory is cached for up to three seconds; no public pull/delete/load endpoint is exposed.

Example model entry (illustrative):

```json
{
  "id":"qwen3:0.6b",
  "object":"model",
  "owned_by":"local",
  "installed":true,
  "digest":"exact-installed-artifact-digest",
  "size_bytes":522000000,
  "selectable_for":["text_chat"],
  "default_for":[],
  "rankings":{"text_chat":{"rank":2,"metrics":{"passed":12,"total":14},"evidence":"benchmarks/round3/rankings.json","profile":{"max_image_edge":640,"num_ctx":2048,"num_batch":32}}},
  "blocked_reason":null
}
```

The response also includes `policy_id` and `defaults` filtered to the caller's permitted tasks. `selectable_for` is the authoritative selection list for that key. A package can be installed yet have an empty list, with reason `not_tested_for_your_jobs` or `artifact_changed_since_test`. The API does not equate installation, capability claims and successful eligibility tests.

`GET /v1/job-types` lists each allowed task's ranked default and currently selectable installed alternatives in `available_models`. Unknown or untested models are never downloaded on demand.

## Use automatic defaults

Omit `model`, use `"model":"auto"`, or use the task name as a default alias. For example:

```json
{"task":"text_chat","model":"auto","input":{"messages":[{"role":"user","content":"Help me find a swimming activity."}],"max_tokens":128}}
```

```json
{"task":"image_recognition","model":"auto","input":{"image_base64":"<bytes>"}}
```

Submit either to `POST /v1/jobs`, then poll `GET /v1/jobs/{id}`. Existing `POST /v1/chat/completions` also accepts `model: auto` or an omitted model. The Camera moderation alias `POST /v1/moderation/jobs` accepts optional `model` beside `image_base64`.

Pandora already submits `auto`. Operator scripts and `.env.example` now default to `auto`. ClassScout's ignored local `.env.local` has `LOCAL_AI_MODEL=auto`; restart its local process to pick that up. **No ClassScout code or Vercel Production variable was changed.** Any other deployed client that hard-codes a model ID must set `LOCAL_AI_MODEL=auto` (or omit the model) to follow future winners. The ClassScout source fallback remains a concrete Qwen ID if no environment setting overrides it.

## Select an alternative deliberately

First discover a model whose `selectable_for` includes the intended task. Supply its actual installed ID:

```json
{"task":"text_chat","model":"qwen3:0.6b","input":{"messages":[{"role":"user","content":"Reply briefly."}],"max_tokens":128}}
```

```json
{"task":"image_recognition","model":"hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0","input":{"image_base64":"<bytes>"}}
```

Chat-compatible clients can set `model` directly on `/v1/chat/completions`. `input.model` is also accepted for text jobs; conflicting top-level/input model choices return 400. A concrete ID now **always selects that actual model**. The previous temporary Qwen-to-Granite legacy alias has been removed so users can genuinely choose Qwen. Use `auto` for defaults rather than relying on an old concrete ID being remapped.

Models are checked for task eligibility, presence on disk and exact tested digest at submission and again before execution. Existing tenant permissions still apply: Camera cannot run text jobs, and ClassScout/Habigoal cannot request images. Model choice does not bypass the common FIFO queue, memory limits, prompt restrictions or human-review-only moderation semantics.

Image inference honors the chosen model's tested input profile, including Granite Vision's 320-pixel maximum. `normalized_sha256` describes the gateway's normalized image; additional model-specific downscaling may occur. The job's `model_profile` records that effective dimension. General recognition uses its fixed structured-description prompt, and moderation keeps the same versioned nine-category prompt/schema with the chosen tested model. Results can differ in format/quality across alternatives; schemas and test scores are not promises of correctness.

Selection errors include `model_not_tested_for_job`, `model_not_installed`, `default_model_not_installed`, `model_artifact_changed_since_test`, `model_inventory_unavailable` and `model_policy_unavailable`. Handle them as explicit failures, not image clearance or permission to bypass vetting. Explicit unknown/missing model requests use 400; unavailable defaults/inventory/policy use 503.

## Required workflow after new tests

1. Run task-specific eligibility and quality tests under the actual server limits. Keep English, image recognition, moderation and each non-English language separate. Record exact artifact digests, errors, schemas, profiles and latency. A failed/unfinished model never becomes a winner.
2. Update the appropriate canonical ranking. Preserve category-specific moderation evidence and old raw results. Update `config/ranking-sources.json` when a newer ranking supersedes the old source.
3. Run `python3 scripts/promote_rankings.py --write`, inspect winner changes, then `--check` and the unit suite. Missing digest evidence is an error requiring evidence, not permission to invent a digest.
4. Ensure every new default is installed on Hetzner and its digest matches. Stage the reviewed generated policy on the server and atomically replace `/opt/narimato-gateway/config/model-policy.json`. No restart is needed for a policy-only update. Deploy source changes with a drained queue and controlled restart, using the staged update helper when applicable.
5. Verify `/v1/models`, `/v1/job-types`, actual auto completions, explicit alternatives and mixed-job serialization. Confirm the actual response model, not natural-language self-identification. Check Pandora and existing client routes. Document limitations and deploy the documentation with the change.
6. Commit and push the reviewed evidence, generated policy, source-pointer changes and documentation to this repository. Do not include private images, keys or live secret configuration.

A daily server-side metadata-discovery timer is now active; no unattended benchmark/inference schedule was created. See CONTINUOUS-EVALUATION.md. This remains the mandatory completion workflow for every authorized test round. Rebuild config/tested-models.json after tests and refresh the deployed discovery index so known/declined artifacts are not repeatedly shortlisted.

## Verification

[Live model-policy verification](../results/model-policy/public-verification.json) records actual discovery and model choices. [Shared queue guide](JOB-ROUTER.md) covers retention, FIFO limits, circuit recovery, polling and client timeout constraints. `scripts/deploy_gateway_update.py` is the server-side staged source-upgrade helper; it drains the queue, backs up replaced files privately, validates Caddy maintenance and rolls back on readiness failure.
