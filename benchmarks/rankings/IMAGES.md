# General image recognition ranking

Updated with the [Round 5 comparison](../round5/REPORT.md). Same 32-image reference cohort, exact deployed recognition implementation for the new variant; other full-cohort results are historical. Model/profile differences are not a controlled quantization-only experiment.

| Rank | Model | Readiness score | Valid outputs | Object reference F1 | OCR targets | Median seconds |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | minicpm-v4.6:q5_K_M | 93.1% | 32/32 | 89.3% | 8/8 | 24.93 |
| 2 | minicpm-v4.6:1b | 80.7% | 29/32 | 77.0% | 7/8 | 24.15 |
| 3 | qwen3.5:0.8b | 80.0% | 29/32 | 75.9% | 7/8 | 47.64 |
| 4 | hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0 | 70.4% | 26/32 | 68.0% | 6/8 | 6.83 |
| 5 | hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0 | 40.0% | 14/32 | 34.6% | 4/8 | 9.67 |
| 6 | hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0 | 28.7% | 10/32 | 24.0% | 3/8 | 9.69 |

Readiness is a weighted cohort score, not a general accuracy percentage. Old two-image screening, moderation and non-English scores are never mixed into it.
