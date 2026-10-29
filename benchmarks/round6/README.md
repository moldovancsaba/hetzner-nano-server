# Round 6: full suites for four untested checkpoints

Frozen on 2026-10-29 before inference. See `plan.json`, pinned `source-metadata.json` and the metadata-only `input-audit.json`.

- English: all seven frozen source-grounded structured scenarios, twice each, plus one separately scored native tool call. A fresh complete Granite control detects runtime regression. Fourteen checks are repeated trials, not fourteen independent scenarios.
- Hungarian: the text candidates separately receive all 24 strict structured cases, six original free-form cases and five synthetic Habi role/correction probes. This is a separate language evaluation; English is never penalized for Hungarian failure. Assistant chat review is not independent native-speaker certification.
- Recognition: all 32 original public research images, nine robustness variants and eight count probes for each runtime-compatible candidate.
- Moderation: all 41 original research images across nine signals, independently scored. These map only partially to six Camera rejection reasons. Human approval is always required. This is not a new twelve-reason or video benchmark.

Use `run.py` on Hetzner beside the existing `round3`/`round4` fixture helpers and active gateway code. It obtains a renewable idle gateway lease, stages one package at a time, samples real cgroup memory/OOM counters, pauses/restores hourly cleanup, removes temporary candidate packages, and restores the current English runtime. Existing active/queued client work takes priority before acquiring a lease; submissions during a bounded lease may receive retryable maintenance responses. Tests never extend production-demand retention.

Wrong answers do not terminate a suite. Explicit technical/resource safety stops retain partial failures as failures; a three-case smoke run is never reported as a full test. No runtime/cap upgrade, swap, public model-management endpoint, training collection or live Camera/user data is involved. All images stay in ignored/private storage or temporary server copies, not this public Git folder.

The actual production recognition and moderation Runner hardcodes 2048 context/batch32; the plan uses those actual values, not an unused profile override. Text uses the historical English 2048/batch32 profile; Hungarian's separate profile is 2048/batch16. Different tasks and languages are never averaged.

A new ranking winner is not deployable until its exact artifact and required client context profiles have been verified, policy generated/deployed, API discovery and synthetic public jobs checked, and the public dashboard refreshed. Smaller OLMo models declare 4K context and must not silently replace a required 8K default without a compatible verified profile.
