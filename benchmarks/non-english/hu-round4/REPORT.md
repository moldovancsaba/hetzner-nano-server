# Hungarian round 4: Phi-4 Mini — 2026-10-31

**Result: not a candidate.** Phi-4 Mini Instruct (Microsoft, MIT licence) as the community GGUF `unsloth/Phi-4-mini-instruct-GGUF` Q3_K_M did not complete the run: it answered the first two structured cases incorrectly and its native runner was then killed for memory on the third. The run was stopped by its own OOM guard after 3 of 35 cases. The served Qwen3-4B Q3_K_M profile (17/24 structured, 3/6 usable chat) is unchanged, and nothing about the Hungarian route, the English defaults or any other task changed.

## What was tested

- **Why this model:** the one plausible small candidate not yet measured. Its official card lists Hungarian among the supported languages ([follow-up notes](../../../docs/HUNGARIAN-FOLLOWUP.md)).
- **Artifact:** `unsloth/Phi-4-mini-instruct-GGUF` revision `78eb92a46fc37e6b524df991ed9aca9bc6aa7b80`, file `Phi-4-mini-instruct-Q3_K_M.gguf` (2,117,532,640 bytes, sha256 `8eb40b19…7653`); upstream `microsoft/Phi-4-mini-instruct` revision `cfbefacb99257ffa30c83adab238a50856ac3083`. Ollama 0.40.11 recognised the Phi chat template. Installed digest `4eb13d0bc4f4…`.
- **Profile:** context 1024, batch 8, non-thinking, 192 output tokens, temperature 0, under the unchanged 2,800 MiB native memory cap — identical to the served Qwen profile, so memory and scores are like-for-like. Q4_K_M (2.49 GB) does not fit the cap and was not attempted.
- **Cases:** the frozen `fixtures.json` shared with round 2 (sha256 `e9e20c87…201f`): 24 strict structured cases, 6 chat cases and 5 synthetic Habi regressions. Unchanged gate: ≥20/24 structured, ≥5/6 usable chat, complete, zero OOM kills.
- **Procedure:** run on the inference host under the gateway maintenance lease (renewed per case), cleanup timer stopped for the run and restarted afterwards, test-purpose headers, candidate unloaded and removed afterwards, Granite served again at the end. No live payloads.

## Outcome

| Case | Result |
| --- | --- |
| `city-number` | Valid JSON but `"city": "Budapesten"` (the inflected form) instead of `Budapest` — incorrect; 19.6 s including the model load |
| `case-ending` | Valid JSON but the field was named `cityName` instead of `city` — incorrect; 9.2 s |
| `negated-count` | The native runner stopped unexpectedly ("resource limitations") — one OOM kill in the container; the run aborted |

- **Scored:** 0 of 3 structured cases correct, 2 of 3 valid JSON; 3 of 35 cases run; `oom_kill_delta` 1; peak cgroup 2.94 GB (the cap). Free-form chat review and the Habi regressions were not performed (recorded as not performed, not as zero).
- **Median time** of the completed cases: 9.2 s.
- **Memory:** at the same profile Qwen3-4B Q3_K_M (2.07 GB) completes all cases at the cap; Phi-4 Mini Q3_K_M (2.12 GB, 3.84 B parameters, 200K-token vocabulary) does not. A smaller quantization (Q3_K_S 1.90 GB, IQ3_XS 1.84 GB, Q2_K 1.68 GB) might fit, but two wrong answers on the easiest cases give no reason to expect it to pass a 20/24 gate; it was not attempted.

## Host effect and restoration

One OOM kill occurred in the Ollama container at about 10:16 UTC, during the maintenance lease, while no gateway job was running. Afterwards the candidate was unloaded and removed (10 models installed as before), Granite 4 1B-H answered the readiness probe and is resident, the cleanup timer is active, the monitor reports no alerts, and the queue is idle.

## Files

[plan.json](plan.json) · [fixtures.json](fixtures.json) · [run.py](run.py) · [results.json](results.json) · [run.log](run.log) · [score.py](score.py) · [rankings.json](rankings.json)

## Limits of this evidence

Three cases are not a Hungarian quality measurement of the model; they show that this artifact does not run reliably in the available memory at the served profile, which already decides the question for this host. The remaining routes to a better Hungarian model are a larger host or an external service ([follow-up notes](../../../docs/HUNGARIAN-FOLLOWUP.md#other-candidates-and-constraints)).
