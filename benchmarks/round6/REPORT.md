# Round 6 results

Four new exact checkpoints, 2026-10-29 08:59–10:11 UTC (72 minutes) under the exclusive maintenance lease. English, Hungarian, general-image recognition and moderation are scored separately and never averaged. **No ranking leader changed.** English stays **granite4:1b-h**, recognition **minicpm-v4.6:q5_K_M**, moderation **qwen3.5:0.8b**, Hungarian (experimental) unchanged.

| Model | Task | Outcome | Result |
| --- | --- | --- | --- |
| hf.co/LiquidAI/LFM2-1.2B-GGUF:LFM2-1.2B-Q4_K_M.gguf | English text | completed, not promoted | 8/14 checks; no native tool support |
| | Hungarian (separate) | gate failed | 2/24 strict structured against the unchanged 20/24 gate |
| hf.co/allenai/OLMo-2-0425-1B-Instruct-GGUF:Q4_K_M | English text | completed, not promoted | 8/14 checks; no native tool support; 4K declared context cannot replace the verified 8K default |
| | Hungarian (separate) | gate failed | 0/24 strict structured |
| hf.co/ggml-org/SmolVLM2-256M-Video-Instruct-GGUF:Q8_0 | Recognition | stopped by contract rule | 0/3 usable: three consecutive incomplete image responses; robustness not run; counting 0/8 |
| | Moderation (separate) | completed | 38/41 valid; macro F2 0.160 against 0.694 for the default; median 48.6 s |
| hf.co/bartowski/OpenGVLab_InternVL3_5-1B-GGUF:Q4_K_M | Recognition | **incomplete — runner fault** | 9 of 32 cases returned; no OOM; robustness, counting and moderation never ran |

A fresh complete Granite control scored 14/14, so there was no runtime regression. No candidate recorded an OOM kill. The runtime was unchanged (Ollama 0.40.11, 2800 MiB cap, 2048 context / batch 32 for the comparable English and image profiles, 2048/batch 16 for Hungarian).

## InternVL3.5 1B is not a quality verdict

The first run stopped InternVL with an unhandled `StopIteration` (empty message) after 9 recognition responses (median about 49 s, p95 about 85 s, sampled cgroup memory at the 2800 MiB ceiling including page cache). The later `resume.py` pass treated that earlier stop as final and finished it in seconds without retrying. The cause is a defect in the runner's stop and resume handling, not evidence about the model. It is recorded in `config/model-decisions.json` as `incomplete_runner_stop`, left unranked, and its moderation is deliberately absent from the moderation tables rather than published as a zero. Re-running needs a fixed harness and about two hours of exclusive inference, which interrupts production admission, so it needs an owner-approved maintenance window (backlog RN-01). Repeating it on the unfixed harness is barred.

## Method and limits

- English: all seven frozen source-grounded scenarios, twice each (fourteen repeated checks, not fourteen independent scenarios), plus one separately scored native tool call.
- Hungarian: the 24 strict structured cases scored by the unchanged exact-match rule. The free-form chat review and the five synthetic Habi regressions were not performed for these two models because they missed the structured gate by a wide margin; they are recorded as "not performed", not as zero. This is not native-speaker certification. LFM2 also hit one token-repeat error in the Hungarian suite (the stop rule was narrowed so that a single such error no longer ends the whole language suite).
- Recognition: 32 public research images, nine robustness variants and eight counting probes for a runtime-compatible candidate. Moderation: the same 41 images across nine signals, which map only partially to six of Camera's twelve rejection reasons. Human approval is always required.
- Candidates were staged one at a time, the cleanup timer was paused and restored, every candidate package was removed afterwards, and the artifact digests are retained in `artifact-audit.json` and the decision register. The final restore check returned Granite READY and the cleanup timer was active again. No production payloads, live Camera images or training exports were involved.
- Two things are different from earlier rounds: the run was checkpointed once at an idle lease (see `results.json` continuations) and `complete_hungarian.py`, `complete_vision_tasks.py` and `resume.py` finished tasks independently. Partial failures are kept as failures.

See the [raw run](results.json), [plan](plan.json), [pinned sources](source-metadata.json), [input audit](input-audit.json), [artifact audit](artifact-audit.json), [merged rankings](rankings.json), [recognition detail](recognition-summary.json), [moderation detail](moderation-new-summary.json) and the [Hungarian follow-up](../non-english/hu-round3/rankings.json).

## Deployment

**Pending: not yet deployed.** Defaults are unchanged. The regenerated `config/model-policy.json` (policy id `2fa66c02…`) only adds the three tested models that are not installed (they stay blocked), shifts lower English ranks by two and leaves the top three per task untouched, so the cleaner's retention set is the same. The live gateway still serves the previous policy id (`feecd620…`) and the public dashboard on the server still shows 48 variants, because the production deploy was held for owner approval. `deploy_policy.py` in this folder is prepared for that step (it never pulls weights and verifies installed digests) but has not been run, and `deployment.json` does not exist yet. Until then this round is closed in the repository and open in production.
