# InternVL corrected continuation — 2026-11-01

The owner requested continuation of the full tests. The original Round 6 recorded nine recognition responses, then stopped because of a harness defect. That original evidence remains unchanged in `results.json`.

`complete_internvl.py` resumes only unattempted cases against the same frozen image hashes and native model digest. It requires all 32 recognition images, nine robustness variants, eight counting probes and 41 moderation images, plus the moderation injection probe, subject to the original technical safety stops. Scores stay separate by task. This is a continuation of an existing checkpoint, not another unique tested model.

The fix makes `prepare()` consult current inventory rather than a startup snapshot. This prevents an imported model that was subsequently removed from being mistaken for an installed model. Two regression tests cover reuse and reinstallation. The continuation explicitly selects the incomplete InternVL run rather than treating its prior `failed` status as final.

The live test runs on the existing CPU server with the unchanged 2800 MiB Ollama cap. It waits for an idle queue, then holds a renewable maintenance lease while running the remaining cases. Public inference admission receives retryable maintenance responses during that lease. No client payloads are collected. The cleanup timer is stopped only after the lease is acquired; the runner unloads and removes its temporary candidate, restores Granite, and re-enables cleanup in `finally` before releasing the lease.

Results are saved atomically after each case in `internvl-completion.json`. The separate `score_internvl.py` refuses unfinished or unrestored evidence. A completed run must still be reviewed, reflected in task rankings and policy, and published to the dashboard before this work is considered delivered. No model is promoted merely because it returns valid JSON.

Status at launch: running; no new quality conclusion yet. Do not treat this file as a completion report.
