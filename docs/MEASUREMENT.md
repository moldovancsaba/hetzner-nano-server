# Measurements and evaluation

## Historical observations from setup

| Test | Result | Interpretation |
| --- | --- | --- |
| Native chat, think false, READY | 5.83 s total; 2 output tokens; reported generation 11.69 tokens/s | Includes model loading/input work; not a throughput benchmark |
| OpenAI chat relying on /no_think, cap 100 | 9.66 s; 100 completion tokens; empty final content | Failed useful-output test; use explicit reasoning_effort none |
| OpenAI JSON classification, reasoning none | 3.48 s; 31 completion tokens; valid category/summary | One English synthetic example, not product accuracy evaluation |
| Public HTTPS READY after DNS worked | 0.20 s | Warm, tiny prompt and repeated input; likely cache benefit; not a general latency promise |
| Missing-key inventory | HTTP 401 | Authentication rejection verified |
| Both project keys inventory | HTTP 200; qwen3:1.7b | Both intended keys accepted |
| Loaded idle container | About 1.645 GiB / 2.734 GiB cap | Snapshot, not peak generation memory |
| Host available memory after load | About 1.7 GiB of 3.7 GiB total | Linux available memory; not raw free memory |

## Reproduce now

```sh
python3 scripts/healthcheck.py --project classscout
python3 scripts/benchmark.py --project classscout --runs 5
sh scripts/server.sh status
```

The benchmark makes sequential short authenticated synthetic requests and records UTC timestamps, wall latency, HTTP status, token usage and narrow deterministic checks. It never saves credentials. It sends only synthetic test content. Native historical tokens/second excludes loading/input; the new script's wall latency includes network and request overhead. Compare like with like.

Inspect results/*.json. Small sample p50/p95 are descriptive only; they are not an SLA or a statistically stable tail estimate. Warm/cache state, shared CPU contention and model retention affect measurements. Avoid concurrent benchmark runs while production is using this single worker.

## Real acceptance plan

Create an owner-approved, privacy-conscious evaluation set of at least 30-50 realistic examples per workflow and supported language. Label expected classification/extraction fields or score summaries for factual support, completeness and readability. Track JSON validity, schema validity, task accuracy, hallucination rate, refusals when information is missing, timeout/error rate and latency distribution. Test indirect prompt injection with untrusted source text treated as data.

Measure separately: first request after unload; warm different prompts; repeated prompts; input sizes; requested output lengths; streaming time to first token and total latency; concurrency 1 then 2 at low volume; queue saturation in an isolated maintenance window. Capture peak RSS/container memory, CPU, disk usage and OOM/restart counts. Do not stress production without an agreed window.

Set latency and quality targets from each product workflow, then compare 0.6B/1.7B models or a larger server on the same examples. Cost per successful task includes server/add-ons, failures/retries and operator effort. No monthly task capacity or cost per request has yet been established.

## Saved baseline: 2026-10-26 21:22 Europe/Budapest

`results/benchmark-20261026T192229Z.json` records five sequential public HTTPS requests: all HTTP 200 and all valid JSON; three of five passed the strict expected-value checks. Median wall latency was 1.3734 s; nearest-rank p95 was 1.5226 s (five samples only).

Failures are retained, not rerun away:

- Asked to count two morning and three evening classes, the model returned total 2 instead of 5. Arithmetic should be deterministic application code.
- Asked for a lowercase language string for learning French, it returned `fr`. This is semantically a valid language code, but the strict check expected `french`; the prompt did not explicitly forbid codes. This shows an underspecified output contract, not a proven failure to recognize the language. Future evaluation should explicitly specify a full-name enum or an ISO-code schema.

The benchmark exits 1 when any expected value fails. This baseline's nonzero exit is a recorded quality outcome, not a script crash. Both project health checks passed all missing-key, invalid-key, and valid-key assertions; saved in results/health-*-2026-10-26.json. New version/listener and server snapshots are saved beside them.

## Capability benchmark extension

See ../benchmarks/capabilities/REPORT.md and results.json: six text models on seven cases repeated twice, one vision model on three cases repeated twice, native function-call tests and two reload trials per model. Additional real Atlas tool flow passed with validated arguments and selected ID. The original qwen3:1.7b model was restored. All text candidates failed the included prompt-injection test. Treat small-model data as untrusted; preserve deterministic application constraints.

## Separate vision and text/chat extension

See ../benchmarks/round2/REPORT.md for attempted Gemma 4 packages, other vision models, image-specific context/resolution/batch retries, JSON-schema output checks, and independent text/chat comparisons. SmolVLM2 Q4 passed 12/12 at 640x480 and Granite Vision passed 12/12 at 320x240; both passed 5/5 strict schema cases. These are two controlled images and repeated prompts, not broad production accuracy. First new-image times were tens of seconds. Failed model loads are not quality scores.

## Language evaluation policy

Non-English capabilities are managed completely separately in ../benchmarks/non-english/REPORT.md. Current English results are projected to ../benchmarks/round2/english-results.json and exclude Hungarian tests from correctness, JSON validity, latency and recommendations. Historical mixed raw observations are preserved. Each language and task needs independent evaluation and acceptance; no combined multilingual score or English gating is permitted.

## Expanded model comparison

Round3 tested eleven additional variants with English-only text and independent image checks, keeping non-English evidence separate. Updated comparable fourteen-check English and five-check image rankings are in ../benchmarks/rankings/. The image list now contains ten completed variants, with several accuracy ties. A separate 1024-token English reasoning smoke check distinguishes short-budget incompatibility from general reasoning ability. See ../benchmarks/round3/REPORT.md for configurations, model digests, raw failures and resource/cleanup verification.
