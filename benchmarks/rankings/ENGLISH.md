# English structured text ranking

Updated with [round 4](../round4/REPORT.md). Small controlled screening, not a global leaderboard. Moderation and non-English remain independent.

| Rank | Model | Correct | JSON valid | Native tool | Median seconds |
| --- | --- | --- | --- | --- | --- |
| 1 | granite4:1b-h | 14/14 | 14/14 | True | 3.028 |
| 2 | qwen3:0.6b | 12/14 | 14/14 | True | 1.110 |
| 3 | qwen3:1.7b | 12/14 | 14/14 | True | 2.010 |
| 4 | qwen2.5:0.5b | 10/14 | 14/14 | True | 0.829 |
| 5 | hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M | 10/14 | 14/14 | True | 1.256 |
| 6 | granite3.3:2b | 10/14 | 14/14 | True | 3.107 |
| 7 | granite4:350m | 10/14 | 14/14 | True | 3.360 |
| 8 | qwen2.5-coder:0.5b | 10/14 | 14/14 | False | 0.796 |
| 9 | qwen2.5:1.5b | 8/14 | 14/14 | True | 2.066 |
| 10 | llama3.2:1b | 8/14 | 14/14 | False | 1.633 |
| 11 | smollm2:1.7b | 8/14 | 12/14 | True | 2.140 |
| 12 | granite3.1-moe:1b | 6/14 | 14/14 | False | 0.903 |
| 13 | hf.co/QuantFactory/EuroLLM-1.7B-Instruct-GGUF:Q4_K_M | 5/14 | 12/14 | False | 2.237 |
| 14 | gemma3:1b | 4/14 | 14/14 | False | 2.683 |
| 15 | smollm2:360m | 0/14 | 10/14 | False | 4.469 |
| 16 | smollm2:135m | 0/14 | 8/14 | False | 2.548 |

Correctness determines ranking first. Timing tie-breaks are descriptive and sensitive to cache/runtime conditions; they do not establish statistical quality superiority. Current defaults must match the generated task policy and verified context requirements.
