# General still-image recognition ranking

Updated with [round 4](../round4/REPORT.md). Small controlled screening, not a global leaderboard. Moderation and non-English remain independent.

| Rank | Model | Correct schema | Raw checks | Image edge | First photo seconds | First poster seconds |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0 | 5/5 | 10/12 | 640 | 5.6756 | 4.5614 |
| 2 | hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0 | 5/5 | 10/12 | 640 | 6.0521 | 4.6066 |
| 3 | hf.co/LiquidAI/LFM2-VL-1.6B-GGUF:Q8_0 | 5/5 | 12/12 | 640 | 19.1467 | 16.6778 |
| 4 | hf.co/LiquidAI/LFM2.5-VL-1.6B-GGUF:Q4_K_M | 5/5 | 12/12 | 640 | 19.5999 | 17.4117 |
| 5 | minicpm-v4.6:1b | 5/5 | 12/12 | 640 | 22.1375 | 20.3348 |
| 6 | hf.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF:Q4_K_M | 5/5 | 12/12 | 640 | 45.7948 | 36.7059 |
| 7 | granite3.2-vision:2b | 5/5 | 12/12 | 320 | 55.8249 | 53.0938 |
| 8 | hf.co/ggml-org/SmolVLM2-500M-Video-Instruct-GGUF:Q8_0 | 4/5 | 8/12 | 640 | 8.9096 | 8.0074 |
| 9 | hf.co/ggml-org/SmolVLM-500M-Instruct-GGUF:Q8_0 | 3/5 | 4/12 | 640 | 11.6969 | 8.7731 |
| 10 | qwen3.5:0.8b | 3/5 | 6/12 | 640 | 47.6757 | 44.5117 |
| 11 | hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0 | 2/5 | 6/12 | 640 | 5.8458 | 4.6079 |
| 12 | hf.co/ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0 | 2/5 | 4/12 | 640 | 7.7136 | 7.7336 |
| 13 | moondream:1.8b | 2/5 | 0/12 | 640 | 30.0797 | 26.5006 |

Correctness determines ranking first. Timing tie-breaks are descriptive and sensitive to cache/runtime conditions; they do not establish statistical quality superiority. Current defaults must match the generated task policy and verified context requirements.
