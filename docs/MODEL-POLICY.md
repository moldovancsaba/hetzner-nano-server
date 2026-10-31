# Ranked defaults and client model selection

## Standing policy

**Default services always use the best eligible model in the current ranking for their job.** Future testing exists to improve those assignments. Completing a new benchmark means updating its ranking evidence, rebuilding/deploying this policy and verifying the live defaults; leaving the previous winner deployed is unfinished work.

Rankings remain separate. Current defaults:

| Job | Ranking | Default |
| --- | --- | --- |
| English text / ClassScout / Pandora | English structured-task ranking | `granite4:1b-h` |
| General Camera image recognition | Broader actual-service image ranking | `minicpm-v4.6:q5_K_M` |
| Camera forbidden-content assistance | Broader nine-category moderation ranking | `qwen3.5:0.8b` |

Recognition follows the frozen broader cohort plus the [Round 5 exact-service-implementation comparison](../benchmarks/round5/REPORT.md). The new Q5 variant leads the measured recognition ordering; this does not isolate precision from operating-profile changes. Moderation follows the independent [41-image comparison](../benchmarks/vision-evaluation/REPORT.md) and keeps human-review-only semantics. Qwen3.5 ranks narrowly above MiniCPM on equal-category macro F2 (0.694 versus 0.690), at higher latency; this is a provisional cohort ordering, not demonstrated general superiority. Its bounded image profile explicitly disables thinking. All six completed recognition candidates are selectable if their exact tested artifacts are installed; historical screening alternatives have no comparable current rank. English structured-task results remain a text-selection proxy; non-English and movies are separate unapproved workstreams.

Hungarian is a separate explicit **experimental** `text_chat_hu` job. No candidate met its quality gate; the best complete resource-valid profile is exposed for owner-requested testing/feedback only, with human review. See [the Hungarian API guide](HUNGARIAN.md). Its scores never enter English/image rankings.

## One machine-readable policy

- `config/ranking-sources.json` selects the current canonical ranking/result sources. Point it to the new round when adding a newer canonical ranking; do not create conflicting current rankings.
- `scripts/promote_rankings.py --write` derives **config/model-policy.json** from those sources. Despite its name, this script only builds model policy; it does not publish anything to GitHub or deploy a service.
- The generated file contains task winners, model/task ranks, benchmark metrics, tested profiles, exact tested artifact digests, source hashes and a deterministic policy ID.
- `--check` fails if that file is stale or inconsistent with its source evidence. Unit tests also enforce this.
- `config/job-routes.json` controls tenant permissions only; it no longer hard-codes a second set of model choices. Its `ranking_task` fields are not read by any code.
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
4. Pause the automatic model-cleanup timer before pulling/testing unranked temporary candidates. Ensure every new default is installed on Hetzner and its digest matches. Stage the reviewed generated policy on the server and atomically replace `/opt/narimato-gateway/config/model-policy.json`. No restart is needed for a policy-only update. Deploy source changes with a drained queue and controlled restart, using the staged update helper when applicable. Restore/verify production and re-enable cleanup after the test/update window.
5. Verify `/v1/models`, `/v1/job-types`, actual auto completions, explicit alternatives and mixed-job serialization. Confirm the actual response model, not natural-language self-identification. Check Pandora and existing client routes. Document limitations and deploy the documentation with the change.
6. Commit and push the reviewed evidence, generated policy, source-pointer changes and documentation to this repository. Do not include private images, keys or live secret configuration.

A daily server-side metadata-discovery timer is now active; no unattended benchmark/inference schedule was created. See CONTINUOUS-EVALUATION.md. This remains the mandatory completion workflow for every authorized test round. Rebuild config/tested-models.json after tests and refresh the deployed discovery index so known/declined artifacts are not repeatedly shortlisted.

## Verification

[Live model-policy verification](../results/model-policy/public-verification.json) records actual discovery and model choices. [Shared queue guide](JOB-ROUTER.md) covers retention, FIFO limits, circuit recovery, polling and client timeout constraints. `scripts/deploy_gateway_update.py` is a server-side staged update helper for the five files it lists (`gateway/server.py`, `gateway/catalog.py`, `moderation/server.py`, `config/model-policy.json`, `config/job-routes.json`); it drains the queue, backs up replaced files privately, validates Caddy maintenance and rolls back on readiness failure. It is retired: it does not ship the other modules the gateway imports and refuses to run without an explicit flag. A policy-only change needs no helper: replace `config/model-policy.json` atomically.

## Weight retention

Installed alternatives are now automatically managed by [top-three-per-task plus 3-day production use](AUTO-MODEL-CLEANUP.md). Tests must mark X-Request-Purpose: test and do not extend retention. API model discovery reflects evictions; evidence remains in the registry/repository. Missing alternatives are not downloaded automatically.

## Paperclip context profile (2026-10-27)

The ranked model winners are unchanged. `config/runtime-context-profiles.json`, referenced by ranking-sources.json, adds a verified **8192-token text** profile for the exact existing Granite artifact. It records the native long-input, fourteen-check compatibility and memory evidence; the generator includes those source hashes. ClassScout, Habigoal and Pandora now share the verified 8192-token default Granite profile. Explicit non-Paperclip alternative model pins retain their original tested profiles. `select(..., tenant=...)` and authenticated discovery expose the effective caller profile; the gateway records it with the job and passes it to the native runner. A different ranked winner or explicit model without a verified Paperclip profile is rejected until evaluated; no silent short-context fallback occurs.

See [context test evidence](../benchmarks/paperclip-context/README.md). This is a context/runtime acceptance check, not a new cross-model quality ranking. Existing correctness scores retain their original benchmark profile.

The generated tenant_context_minimums requires 8192 for automatic default text selection by ClassScout, Habigoal, Pandora and Paperclip. The policy generator refuses an automatic winner without corresponding context evidence. Runtime selection also fails explicitly if that guarantee is absent. The base 2048 benchmark profile remains the historical scoring profile; these are per-tenant execution profiles. See CHATBOT-CONTEXT.md.

## Broader recognition comparison (28 October 2026)

The recognition ranking uses 32 real service-contract image cases, nine paired robustness variants and eight separate count probes. This comparison made MiniCPM-V 4.6 1B the default: cohort readiness score 0.807, 29/32 usable responses and 7/8 OCR targets, with median inference about 24 seconds. Qwen3.5 0.8B is close in measured score and about twice as slow; paired uncertainty intervals overlap. The later Round 5 comparison placed MiniCPM-V 4.6 Q5_K_M first on the same cohort (readiness 0.931, 32/32 usable responses, 8/8 OCR targets, median about 25 seconds), and it is the current default; the 1B variant ranks second. These are cohort-specific results, not general accuracy or standalone safety certification. See [the completed recognition report](../benchmarks/vision-evaluation/REPORT-RECOGNITION.md).

Current comparable image rows expose ranking_tier=broader_service_evaluation and current_rank. Older screening variants remain explicit alternatives with ranking_tier=legacy_screening_not_comparable, current_rank=null, and a rank sentinel above 1000 so they cannot be mistaken for current top-five results or retained solely by an old score. Exact tested digests still apply.

Qwen image jobs use the tested think=false profile. Its earlier nine failing as-is-profile requests are diagnostic evidence, excluded from the corrected-profile comparison. Bounded image JSON jobs must not spend their response allowance on reasoning.

Moderation has its own ranking, the broader nine-category 41-image evaluation by macro F2, and its default is Qwen3.5 0.8B. Recognition scores never choose the moderation default. Counting probes are not a count API: six one-object and two two-object scenes give an always-one baseline of 6/8; MiniCPM scored 5/8, so no broad counting claim follows from the recognition win.
