# Moderation model ranking

Current ranking uses the [broader nine-category evaluation](../vision-evaluation/REPORT.md). This is human-review assistance, never automatic approval/rejection.

Order: equal-category macro F2, specificity, valid-response rate, then latency. Invalid/abstained positive references count as missed detection. Sparse positives, unknown references and per-category recall intervals remain visible. General images and non-English are separate.

| Rank | Model | Macro F2 | Macro recall | Macro specificity | Valid responses | Median seconds |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | qwen3.5:0.8b | 0.6943 | 0.7370 | 0.9488 | 41/41 | 37.89 |
| 2 | minicpm-v4.6:1b | 0.6897 | 0.7648 | 0.7799 | 41/41 | 22.44 |
| 3 | hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0 | 0.4502 | 0.4315 | 1.0000 | 41/41 | 7.33 |
| 4 | hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0 | 0.3407 | 0.8426 | 0.2708 | 36/41 | 7.40 |
| 5 | hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0 | 0.2184 | 0.5833 | 0.4991 | 40/41 | 6.62 |
| 6 | hf.co/ggml-org/SmolVLM2-256M-Video-Instruct-GGUF:Q8_0 | 0.1596 | 0.2537 | 0.4472 | 38/41 | 48.61 |

Historical screening alternatives are explicit-only and not numerically comparable to this cohort:
- hf.co/LiquidAI/LFM2.5-VL-1.6B-GGUF:Q4_K_M ([evidence](../../benchmarks/moderation/summary.json)).
