# 4K versus 8K for Paperclip

Measured on 2026-10-27 on our existing 2-vCPU ARM64 inference server. Granite 4 1B Hybrid, num_batch=128, temperature=0, identical JSON schema and ten output tokens. The model was unloaded before every call to avoid prompt-cache reuse; weights remained in the operating-system file cache. Window order was reversed for the second prompt. One run per input/window combination: descriptive comparison, not a statistically stable latency benchmark.

| Actual input tokens | 4K total seconds | 8K total seconds |
| --- | --- | --- |
| 1203 | 27.702 | 27.586 |
| 1995 | 42.590 | 43.016 |

All four responses returned the correct synthetic code. Total times include approximately four to five seconds of model loading. Prompt-only times were also nearly identical: 22.030 vs 22.284 seconds for 1203 tokens, and 37.751 vs 37.627 for 1995 tokens. Peak sampled anonymous memory was 1909.0 MiB at 4K versus 1942.3 MiB at 8K; about 33 MiB difference. No new OOM kill was observed.

Recommendation: keep Paperclip at 8K. With the current 1536-token conservative template reserve and a requested 1024-token output budget, 4K leaves 1536 counted input tokens, while 8K leaves 5632. That input includes submitted instructions, tool schemas, source excerpts and history. For the default 256-token output request, the equivalent input budgets are 2304 and 6400. Increasing capacity does not require filling it; compact actual prompts provide the main speed improvement. The planned research/support worker benefits from the additional space.

Production profile, model ranking and other tenant settings were not changed by this comparison. The existing approved Paperclip profile remains 8192 tokens. The benchmark restored the cleanup timer and released the maintenance lease; no public inference port or new model artifact was introduced.
