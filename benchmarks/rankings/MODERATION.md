# Moderation model ranking

Independent human-review-assistance ranking on the 25-image screening test. This is not automatic moderation approval. Per-category failures remain in [the full report](../moderation/REPORT.md).

Order: positive detections, known correct decisions, false positives, then median latency. Unknown/review is not a correct negative. General-image and non-English scores do not enter this ranking.

| Rank | Model | Positive detections | Known correct | False positives | Median seconds |
| --- | --- | --- | --- | --- | --- |
| 1 | hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0 | 8 | 211 | 1 | 7.31 |
| 2 | hf.co/LiquidAI/LFM2.5-VL-1.6B-GGUF:Q4_K_M | 4 | 4 | 0 | 23.99 |
