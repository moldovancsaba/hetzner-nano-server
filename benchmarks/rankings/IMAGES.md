# General image recognition ranking

Current comparable ranking uses the [broader actual-service evaluation](../vision-evaluation/REPORT-RECOGNITION.md), not the old two-image screening. English, moderation and non-English remain separate.

| Rank | Model | Readiness score | Usable responses | Object reference F1 | OCR targets | Median seconds |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | minicpm-v4.6:1b | 80.7% | 29/32 | 77.0% | 7/8 | 24.15 |
| 2 | qwen3.5:0.8b | 80.0% | 29/32 | 75.9% | 7/8 | 47.64 |
| 3 | hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0 | 70.4% | 26/32 | 68.0% | 6/8 | 6.83 |
| 4 | hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0 | 40.0% | 14/32 | 34.6% | 4/8 | 9.67 |
| 5 | hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0 | 28.7% | 10/32 | 24.0% | 3/8 | 9.69 |

The score is cohort-specific, not a general accuracy percentage. Older variants retain their historical [screening evidence](../round4/rankings.json) and may remain explicit alternatives, but their old scores are not numerically mixed into this ranking.
