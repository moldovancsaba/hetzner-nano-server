# Image analytics ranking

Ten completed model variants on two controlled fixtures. These are not ten independent architectures or a worldwide leaderboard. Order uses the five schema-constrained checks, then tested resolution and mean first-photo/poster time. Small time differences within accuracy ties are descriptive, not evidence of broad statistical superiority.

| Rank | Model | Correct schema values | Input dimension | First photo seconds | First poster seconds |
| --- | --- | --- | --- | --- | --- |
| 1 | LFM2-VL-450M Q8 | 5/5 | 640 | 5.68 | 4.56 |
| 2 | LFM2.5-VL-450M Q8 | 5/5 | 640 | 6.05 | 4.61 |
| 3 | LFM2-VL-1.6B Q8 | 5/5 | 640 | 19.15 | 16.68 |
| 4 | LFM2.5-VL-1.6B Q4 | 5/5 | 640 | 19.60 | 17.41 |
| 5 | SmolVLM2-2.2B Q4 | 5/5 | 640 | 45.79 | 36.71 |
| 6 | granite3.2-vision:2b | 5/5 | 320 | 55.82 | 53.09 |
| 7 | SmolVLM2-500M-Video Q8 | 4/5 | 640 | 8.91 | 8.01 |
| 8 | SmolVLM-500M Q8 | 3/5 | 640 | 11.70 | 8.77 |
| 9 | SmolVLM-256M Q8 | 2/5 | 640 | 7.71 | 7.73 |
| 10 | moondream:1.8b | 2/5 | 640 | 30.08 | 26.50 |

The 450M Liquid variants tie on correctness and process the first photo in about 6 seconds. LFM2.5-VL-450M is a strong current-generation pilot candidate; the small timing advantage of the older variant alone does not establish a better general model. Use explicit output schemas. Most of these tests are large-font OCR, simple counting and shapes; validate on unseen real project photos before production acceptance.

Gemma 4, Qwen3-VL and Ministral did not complete the prior eligibility tests under our limits; they have no image-quality rank here. These are different findings from low-quality outputs.

[Full results and method](../round3/REPORT.md). No image upload endpoint was deployed by this benchmark. New candidate weights were removed after recording results to preserve disk.
