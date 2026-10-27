# Expanded candidate benchmark: English and image analytics

This round continues testing on the existing Hetzner CAX11 (4 GB, 2 ARM64 CPUs). English text/chat and image analytics are separate. Non-English data, scoring and approval remain entirely in ../non-english/.

## Candidates

Main batch: Liquid LFM2.5 text 1.2B Instruct Q4 and 2.6B Q4, Granite 3.1 MoE 1B, DeepSeek R1 1.5B, Phi-3.5 Mini 3.8B; Liquid LFM2.5 vision 450M Q8 and 1.6B Q4, SmolVLM 256M Q8, and SmolVLM2 500M Video-Instruct Q8. The video-named variant is tested only with still images, not video.

Extra batch: previous-generation Liquid LFM2-VL 450M Q8 and 1.6B Q8. These are distinct model variants, not independent architectures or a worldwide top-ten leaderboard. Exact publisher URLs and settings are in plan.json and plan-extra.json. Liquid model cards label their license lfm1.0; no blanket Apache/open-source license classification is asserted here.

## Resource and deployment policy

The existing 2800-MiB container cap and two-CPU quota are retained. Context is 2048 tokens, num_batch=32, temperature zero. Disk reserve is 4 GiB, with a conservative 2600-MiB allowance before each download. Only one candidate is downloaded/tested at a time. Its tag/digest/details, outputs and timings are saved; only packages newly downloaded by this run are removed afterward. Existing model packages are preserved. New weights are therefore not automatically available for production calls after testing.

Each phase restores qwen3:1.7b in finally during normal termination. Hard process/host failure still requires operator recovery and health checks. No deployment environment or application model setting is changed.

## Tests

English: the same seven cases repeated twice (14 comparable checks): listing selection, no match, unknown-price exclusion, JSON filter plan, OSM fact extraction and injected-source resistance. Two English chat cases repeated twice add four checks: short follow-up recall and unknown-secret refusal. An actual native tool-call check and a free-form English advice sample are recorded separately. No non-English prompt is executed.

Images: same two controlled fixtures as round2, six cases repeated twice (12 checks), followed immediately by five schema-constrained cases while the candidate remains loaded. Field names/types are constrained; expected answer values are not encoded in schemas. A first-photo request is recorded separately. Image size starts at 640x480; an error associated with context/memory/time permits one 320x240 retry, whose configuration is recorded. Context is not silently increased.

A generic JSON animal array where a singular string was requested is a format failure even when the species/count is correct. Read raw answers and schema results separately. Plain numeric count requests do not enter the JSON-validity denominator.

The listing/OSM source facts are cached public data from earlier bounded read-only queries. No new Atlas connection, OSM call or credential transfer is needed for this round. Photo and poster ground truth are documented in ../round2/README.md.

## Interpretation

Small controlled examples and deterministic repetitions are not broad accuracy estimates. We have repeatedly used these fixtures for candidate selection; validate selected models on independent real project examples before production acceptance. New-image times matter more than cached repetitions for image jobs. First-request latency includes loading/encoding/generation. Median warm structured-request times are not an SLA and omit public network overhead.

Some earlier English tests used the default prefill batch; this round consistently uses 32. Correctness cases remain the same, but timing comparisons are between recorded configurations rather than a strict parameter-isolated experiment. Native tool-call failure may reflect runtime/template compatibility, not an intrinsic inability to plan an application tool request.

Reasoning-model output is bounded by the same short-response budget; length truncation or empty final output is a failure of that application profile, not proof that the model cannot solve the task with a larger reasoning budget. Load/import failures are eligibility results, not bad accuracy scores.

## Reproduce safely

Use a new timestamped benchmark directory, preserve previous evidence, and copy fixtures.py, images, cached listing/OSM JSON, image-cases.json, plans and runners. Never overlap two runs against the single inference worker. Run main then extra:

```sh
python3 run.py
python3 run-extra.py
```

continue-extra.py was a temporary within-task sequencing helper waiting on the main completion marker. Do not use it against stale completed output while starting a new main run. It is not a recurring automation.

run-extra.py differs only in plan/output filenames. Both scripts record individual pull time, import metadata, request errors, output, completion reason, timings, OOM-kill delta, cleanup result and disk headroom. Original model restoration and before/after inventories are recorded in the result files. Failed partial pulls may have no registered package to remove; cleanup failure in that case is not deletion of an existing model.

## Always-thinking models

The LFM2.5-2.6B publisher explicitly documents it as always-thinking (https://huggingface.co/LiquidAI/LFM2.5-2.6B#chat-template). A think=false request cannot be assumed to disable its model-level reasoning. Empty, length-limited final answers under the 180-token application budget are profile failures, not a general accuracy verdict.

reasoning-check.py therefore performs one separate English smoke check for selected thinking candidates with empty truncated final answers: explicit think=true and 1024 output tokens, with the same context/memory limits and an extended bounded timeout. It stores only final answer, reasoning presence/character count and metrics, not reasoning text. These results never enter the short-output ranking. finish-reasoning.py waits for the preceding extra-image run; it is a temporary sequential task helper, not a recurring automation.

Public COCO sample images may have appeared in model training. The newly constructed poster and the photo still form only a tiny evaluation set; independent project holdouts are required before broad quality claims.
