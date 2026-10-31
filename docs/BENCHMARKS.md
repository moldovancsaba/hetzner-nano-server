# Benchmarks and rankings: index

Every measurement run on this server, newest findings first. This page only points and summarizes; each report states its own method, cohort, limits and raw evidence. Rankings are separate workstreams and are never combined: English text, general image recognition, moderation, and each non-English language are scored on their own. A valid response is not a correct answer, and scores are specific to their cohort.

The deployed defaults come from these rankings through [MODEL-POLICY.md](MODEL-POLICY.md). The public view, with every attempted variant including failures, is the [results dashboard](https://chatbotapi.haho.ai/benchmarks/) ([how it is built](PUBLIC-DASHBOARD.md)). At the Round 6 publication it listed 52 distinct model IDs in 22 cohorts.

## Current rankings

| Workstream | Ranking | Current leader at last test round |
| --- | --- | --- |
| English text and structured tasks | [ENGLISH.md](../benchmarks/rankings/ENGLISH.md) | Granite 4 1B Hybrid |
| General image recognition | [IMAGES.md](../benchmarks/rankings/IMAGES.md) | MiniCPM-V 4.6 Q5_K_M on the frozen 32-image cohort |
| Image moderation (review assistance only) | [MODERATION.md](../benchmarks/rankings/MODERATION.md) | Qwen3.5 0.8B, narrowly (macro F2 0.694 against 0.690 for MiniCPM); the difference does not establish general superiority |
| Hungarian text (experimental) | [language-specific evaluation](../benchmarks/non-english/REPORT.md) | no model passed the quality gate; the best measured profile is available for explicit testing only |

Live defaults are whatever `/v1/models` and `/v1/job-types` report; this table records the last evidence, not the deployment.

## Reports by round

| Round | Date | What it covers |
| --- | --- | --- |
| [Capabilities](../benchmarks/capabilities/REPORT.md) | 2026-10-27 | Seven candidate models, measured unload and load times, real Atlas and OSM inputs, image tests, raw outputs, integration guidance |
| [Round 2](../benchmarks/round2/REPORT.md) | 2026-10-27 | Separate image and text/chat results. SmolVLM2 2.2B Q4 and Granite Vision passed the image checks under image-specific profiles; Granite 4 1B Hybrid emerged as the English structured-task candidate; Gemma 4 could not complete image inference within the limits. Predates the switch to Granite for text |
| [Round 3](../benchmarks/round3/REPORT.md) | 2026-10-27 | Five further English text and six image variants, with larger-budget checks for two always-thinking candidates |
| [Round 4](../benchmarks/round4/REPORT.md) | 2026-10-28 | Ten candidates (five English text, five general image) with fresh winner controls, correctness and format scores, sampled memory, OOM counters and compatibility failures. Machine-readable ranking: [rankings.json](../benchmarks/round4/rankings.json) |
| [Round 5](../benchmarks/round5/REPORT.md) | 2026-10-28 | gemma3:270m, LFM2.5-350M and MiniCPM-V 4.6 Q5_K_M; Q5_K_M leads recognition on the frozen cohort |
| [Round 6](../benchmarks/round6/REPORT.md) | 2026-10-29 | LFM2 1.2B, OLMo 2 1B, SmolVLM2 256M and InternVL3.5 1B through full separate suites; no ranking leader changed. InternVL3.5 1B is unranked because a runner fault halted it after 9 of 32 cases, which is not a quality verdict |

## Camera: images and moderation

- [Broader moderation comparison](../benchmarks/vision-evaluation/REPORT.md): 41 images, nine categories, five working vision artifacts, with category failures. It replaces the [earlier two-image screening](../benchmarks/moderation/REPORT.md), which stays as historical evidence and does not enter the general image ranking.
- [Recognition comparison](../benchmarks/vision-evaluation/REPORT-RECOGNITION.md): 32 public research photographs, nine paired robustness variants and eight separate counting probes. Across both cohorts there are 70 distinct public research images; no live Camera data and no training use. Live API check: [public-verification.json](../benchmarks/vision-evaluation/public-verification.json); health and temporary-input cleanup: [final-runtime-audit.json](../benchmarks/vision-evaluation/final-runtime-audit.json).
- [Camera's twelve rejection reasons](CAMERA-REJECTION-COVERAGE.md) separates the reasons the API can signal today from unsupported ones; [moderation specialists](../benchmarks/camera-specialists/REPORT.md) records the NSFW classifier follow-up.
- Human review stays authoritative for Camera. Research images and sensitive fixtures are excluded from Git.

## Language and context

- [Non-English capabilities](../benchmarks/non-english/REPORT.md): each language and task needs its own model choice and acceptance; English scores exclude non-English tests. Follow-up: [HUNGARIAN-FOLLOWUP.md](HUNGARIAN-FOLLOWUP.md); API and limits: [HUNGARIAN.md](HUNGARIAN.md).
- [Context profiles](../benchmarks/paperclip-context/README.md): synthetic 4K, 8K, 16K and 32K evidence behind the 8K default text profile ([CHATBOT-CONTEXT.md](CHATBOT-CONTEXT.md)). The comparable cross-model benchmark still uses 2048 tokens; deployed profiles are in [runtime-context-profiles.json](../config/runtime-context-profiles.json).

## Baseline smoke benchmark

The first synthetic check of the original text model (`scripts/benchmark.py`, a sequential smoke test and not a load test): 5 of 5 responses were valid JSON, 3 of 5 passed the strict expected-value checks, median latency 1.37 s. One miss was a wrong arithmetic answer and one an underspecified language format; see [MEASUREMENT.md](MEASUREMENT.md). A single small CPU model is not proven suitable for every project task.

## Running a new round

A round is unfinished until the ranking sources, the generated `config/model-policy.json`, the installed winning artifacts, the deployed policy, API discovery, actual `auto` jobs and the documentation agree. Procedure and gates: [CONTINUOUS-EVALUATION.md](CONTINUOUS-EVALUATION.md), [MODEL-POLICY.md](MODEL-POLICY.md), [AGENTS.md](../AGENTS.md). Then rebuild and publish the dashboard (`scripts/deploy_dashboard.py`).
