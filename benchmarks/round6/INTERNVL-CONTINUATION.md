# InternVL corrected continuation — 2026-11-01

The owner requested continuation of the full tests. The original Round 6 recorded nine recognition responses, then stopped because of a harness defect. That original evidence remains unchanged in `results.json`.

`complete_internvl.py` resumes only unattempted cases against the same frozen image hashes and native model digest. It requires all 32 recognition images, nine robustness variants, eight counting probes and 41 moderation images, plus the moderation injection probe, subject to the original technical safety stops. Scores stay separate by task. This is a continuation of an existing checkpoint, not another unique tested model.

The fix makes `prepare()` consult current inventory rather than a startup snapshot. This prevents an imported model that was subsequently removed from being mistaken for an installed model. Two regression tests cover reuse and reinstallation. The continuation explicitly selects the incomplete InternVL run rather than treating its prior `failed` status as final.

The live test runs on the existing CPU server with the unchanged 2800 MiB Ollama cap. It waits for an idle queue, then holds a renewable maintenance lease while running the remaining cases. Public inference admission receives retryable maintenance responses during that lease. No client payloads are collected. The cleanup timer is stopped only after the lease is acquired; the runner unloads and removes its temporary candidate, restores Granite, and re-enables cleanup in `finally` before releasing the lease.

Results are saved atomically after each case in `internvl-completion.json`. The separate `score_internvl.py` refuses unfinished or unrestored evidence. A completed run must still be reviewed, reflected in task rankings and policy, and published to the dashboard before this work is considered delivered. No model is promoted merely because it returns valid JSON.

## Completed results

Completed **2026-11-01 19:35–20:54 Budapest** (18:35–19:54 UTC), about 79 minutes. The first nine recognition records are inherited unchanged from the original run; all remaining cases were attempted once. The full suite is 32 recognition, nine robustness, eight counting, 41 moderation and one moderation robustness case. Zero new OOM kills. Native resource profile stayed at 2048 context/batch32, no thinking, 2800 MiB cap.

| Task | Outcome |
| --- | --- |
| Recognition | Rank **4**; readiness **0.7111**, **28/32** usable responses, **7/8** OCR targets. Median **74.9 s**, p95 **97.1 s** across all recorded recognition responses. Four incomplete-format failures remain failures. |
| Counting | **7/8** correct on the frozen small counting probes. This is not a general counting capability claim. |
| Recognition robustness | All nine responses returned; the instruction-in-image probe did not introduce the injected false object. |
| Moderation | **41/41** valid; macro F2 **0.7484**, recall **0.7870**, specificity **0.0119**; median **53.3 s**. The frozen F2 ranking places it first, ahead of Qwen's 0.6943. |
| Moderation robustness | The injected “clear” instruction did not suppress the hate-symbol flag on the controlled flag image. One probe is not broad injection assurance. |

### Why the new moderation leader needs careful interpretation

Across known labels, it makes 23 true positive detections, nine false positive detections and only four definite true negatives. **320 of 333 known-negative category checks are uncertain.** These are category-level checks, not 320 separate photos. The predeclared F2 score penalizes missed positives and false positive detections, but does not penalize abstention on negative cases; this explains the high F2 despite almost no definite negative coverage. Human approval is always required. An uncertain category is not clearance.

Following the owner's standing ranking rule, `image_moderation` now defaults to this exact InternVL artifact. `qwen3.5:0.8b` remains an installed explicit override with much higher specificity (.949); no client is secretly remapped when selecting it. English still defaults to Granite, recognition to MiniCPM Q5, and Hungarian remains experimental Qwen. A future scoring-policy change should be declared before a fresh held-out run, for example measuring decisive-negative coverage and review workload alongside recall; this run's metric was not retroactively tuned.

The original runner's `StopIteration` fields remain inherited in the continuation's raw model metadata for audit; the new top-level `status: completed` and per-module statuses describe this corrected run. The old `results.json` is unchanged. Do not interpret the inherited diagnostic as a new failure.

## Restoration, selection and publication

Both experiment runners completed successfully. Granite answered **READY**, cleanup was re-enabled, and the new winning artifact was reinstalled with its tested digest before policy deployment. See [installation](internvl-installation.json), [deployment](internvl-deployment.json), [scored summary](internvl-summary.json), [raw continuation](internvl-completion.json), [current ranking](rankings-with-internvl.json) and [public verification](internvl-public-verification.json).

All **11 public API checks passed**, including automatic text/recognition/moderation selection, deliberate overrides, invalid overrides and model switching. All three consumed synthetic image results were deleted (HTTP 200). Final queue status was `ok`, dashboard defaults matched the deployed policy, and gateway/chat/monitor/cleanup were active. [Final aggregate checks](internvl-final-checks.json).

The [public dashboard](https://chatbotapi.haho.ai/benchmarks/) includes separate corrected-continuation recognition and moderation cohorts. The separate [Marqo binary evaluation](../camera-specialists-round2/README.md) does not enter the nine-category ranking. No new Camera application release, external inference or customer-data capture was involved.
