# Ten new candidates: 28 October 2026

Five English text and five general still-image candidates, new to our test history. Some releases are older; this is not a claim of ten new releases. Moderation and non-English are unchanged.

## Candidate outcomes

| Candidate | Task | Outcome | Correct raw checks | JSON valid | Schema checks | Peak cgroup MiB | OOM kills |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smollm2:135m | text | completed | 0/14 | 8/14 | 0/0 | 1805 | 0 |
| smollm2:360m | text | completed | 0/14 | 10/14 | 0/0 | 2613 | 0 |
| qwen2.5:0.5b | text | completed | 10/14 | 14/14 | 0/0 | 2062 | 0 |
| qwen2.5-coder:0.5b | text | completed | 10/14 | 14/14 | 0/0 | 2062 | 0 |
| hf.co/LiquidAI/LFM3-1.7B-GGUF:Q4_K_M | text | load_failed | 0/0 | 0/0 | 0/0 | 2155 | 0 |
| hf.co/LiquidAI/LFM3-VL-2B-GGUF:Q4_K_M | vision | image_inference_failed | 0/0 | 0/0 | 0/0 | 2344 | 0 |
| hf.co/LiquidAI/d1-omni-600M-GGUF:Q8_0 | vision | image_inference_failed | 0/0 | 0/0 | 0/0 | 1710 | 0 |
| hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0 | vision | completed | 6/12 | 10/10 | 2/5 | 2193 | 0 |
| qwen3.5:0.8b | vision | completed | 6/12 | 10/10 | 3/5 | 2622 | 0 |
| minicpm-v4.6:1b | vision | completed | 12/12 | 10/10 | 5/5 | 2629 | 0 |

## Current-winner controls

These reruns check regression and environment drift. Historical leaderboard timings are retained for existing variants; fresh control results remain separate rather than replacing their rankings based on one timing rerun.
- granite4:1b-h: completed; 14/14 raw checks; 0/0 schema checks.
- hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0: completed; 10/12 raw checks; 5/5 schema checks.

## Eligibility failures and limitations

- hf.co/LiquidAI/LFM3-1.7B-GGUF:Q4_K_M: {"error":"llama-server process has terminated: exit status 1: error loading model: unknown model architecture: 'lfm3'\nerror loading model: unknown model architecture: 'lfm3'"}
- hf.co/LiquidAI/LFM3-VL-2B-GGUF:Q4_K_M: {"error":"llama-server process has terminated: exit status 1: error: Failed to load CLIP model from /root/.ollama/models/blobs/sha256-c5c5b58d544a18da919172d2d0368090ea1a4a351b6feb7f8a326a264a5918ab\nerror loading model: unknown model architecture: 'lfm3'\nerror loading model: unknown model architecture: 'lfm3'"}
- hf.co/LiquidAI/d1-omni-600M-GGUF:Q8_0: {"error":"\"hf.co/LiquidAI/d1-omni-600M-GGUF:Q8_0\" does not support generate"}

Native tests used one renewable maintenance lease, draining the shared queue and temporarily refusing new inference. Cleanup was paused, candidate weights were tested serially and temporary packages removed after recording results/digests. The existing 2800 MiB memory cap, two CPUs, no swap and 2048-token benchmark profile were unchanged. Default service 8K profiles were restored afterward. Native tests do not update production usage.

Seven cached English listing/OSM/prompt-injection cases repeated twice and two controlled images are a screening benchmark, not independent project holdouts or broad accuracy certification. Image schema constraints check format separately from expected visual values. Round-4 raw JSON validators additionally require exact keys for animal/count, remote count, OCR and missing address; older raw checks sometimes allowed extra keys. Therefore raw counts across rounds are descriptive, not a like-for-like leaderboard. The five constrained-schema checks retain the same expected answers and required keys. Tools test argument selection, not autonomous MongoDB/OSM access. No private database credentials, live images or user conversations were used. No video, moderation or non-English claim follows from these results.

Cgroup memory includes page cache; 100 ms sampled peaks may miss shorter spikes. OOM counters are recorded separately. First-image requests include model/encoder startup; repeated-image latency is cache-warm. Empty length-limited reasoning answers are marked budget-incompatible, not intrinsically inaccurate. Pull/import/load failures receive no quality rank.

Publisher URLs, revisions and license metadata are in plan.json and source-metadata.json. LiquidAI artifacts use their custom LFM license; listing a model is not blanket commercial/license approval. No remote model code was executed. Runtime was not upgraded to make a candidate pass.

Raw evidence: [results.json](results.json). Rankings: [rankings.json](rankings.json).

## Deployment outcome

Defaults remain Granite 4 1B Hybrid (text), LFM2-VL 450M (recognition) and LFM2.5-VL 450M (moderation). Qwen2.5 0.5B is the new fourth-ranked text alternative, and MiniCPM-V 4.6 1B is the fifth-ranked image alternative; both matching tested artifacts were installed and exposed through the authenticated API. Other temporary candidate weights were removed. Existing 8K default text profiles were preserved.

All 45 local tests passed with Pillow/tokenizers and the verified Granite tokenizer configured. The initial system Python lacked dependencies; an isolated temporary test environment was used. Policy generation and stale-policy checks passed. Public verification is recorded separately in [public-verification.json](public-verification.json).

The 28 public post-deployment checks passed, including all three automatic task routes, actual model IDs, the preserved 8K profile, authentication and result deletion. Both newly retained explicit alternatives completed real API jobs: [alternative verification](alternative-verification.json). Default Granite residency was restored afterward. Gateway/chat and cleanup/discovery timers are active; about 9 GiB disk remains free. Temporary server image fixtures were removed; all test evidence is retained.
