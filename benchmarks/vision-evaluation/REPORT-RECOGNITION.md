# Broader image evaluation — 28 October 2026

Completed comparison on the real 4 GB / two-CPU ARM64 Hetzner service. Earlier two-image scores were screening results and are not mixed into this leaderboard. English text and non-English rankings are unchanged.

## Recognition: actual Camera service contract

24 COCO photographs plus eight photographed-text cases, with reference labels reviewed before inference. The score is 65% reference-supported object F1 and 35% OCR target recall. Invalid/failed service responses score zero. This is a selected public research cohort, not representative Camera production accuracy.

| Model | Readiness score | Usable API responses | Object F1 | OCR targets | Count probes | Median / p95 seconds |
| --- | --- | --- | --- | --- | --- | --- |
| minicpm-v4.6:1b | 80.7% | 29/32 | 77.0% | 7/8 | 5/8 | 24.15 / 30.68 |
| qwen3.5:0.8b | 80.0% | 29/32 | 75.9% | 7/8 | 8/8 | 47.64 / 56.54 |
| hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0 | 70.4% | 26/32 | 68.0% | 6/8 | 8/8 | 6.83 / 10.12 |
| hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0 | 40.0% | 14/32 | 34.6% | 4/8 | 3/8 | 9.67 / 10.18 |
| hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0 | 28.7% | 10/32 | 24.0% | 3/8 | 2/8 | 9.69 / 10.46 |

Equivalent terms such as tabby cat/cat and sofa/couch are accepted. Compound nouns are disambiguated: hot dog is not dog, teddy bear is not wild bear. Source-supported coarse-object F1 does not certify every color, relationship or sentence in a free-form description. Counting is a native capability probe, not an exposed question/count API. Its six one-object and two two-object scenes give an always-one baseline of 6/8; the eight probes are too small/unbalanced for a broad counting claim.

### Paired uncertainty

- Winner versus qwen3.5:0.8b: point delta 0.7%; descriptive paired 95% interval [-0.1605, 0.1789].
- Winner versus hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0: point delta 10.3%; descriptive paired 95% interval [-0.0547, 0.2651].
- Winner versus hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0: point delta 40.7%; descriptive paired 95% interval [0.2306, 0.5776].
- Winner versus hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0: point delta 52.0%; descriptive paired 95% interval [0.3531, 0.6885].

### Robustness, separate from independent-image counts

Nine paired dim/compression/instruction variants per model, derived from four base cases (the injection case reuses the dog photo). These are not additional independent scenes.

- minicpm-v4.6:1b: dim mean reference score 91.7% (4/4 usable), jpeg mean reference score 89.3% (4/4 usable), visible_instruction mean reference score 100.0% (1/1 usable)
- qwen3.5:0.8b: dim mean reference score 100.0% (4/4 usable), jpeg mean reference score 100.0% (4/4 usable), visible_instruction mean reference score 100.0% (1/1 usable)
- hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0: dim mean reference score 95.0% (4/4 usable), jpeg mean reference score 95.0% (4/4 usable), visible_instruction mean reference score 100.0% (1/1 usable)
- hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0: dim mean reference score 95.0% (4/4 usable), jpeg mean reference score 50.0% (2/4 usable), visible_instruction mean reference score 100.0% (1/1 usable)
- hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0: dim mean reference score 50.0% (3/4 usable), jpeg mean reference score 50.0% (2/4 usable), visible_instruction mean reference score 100.0% (1/1 usable)

## Scope and evidence

32 distinct primary photographs; paired robustness/count probes are not extra independent scenes. Public annotations plus one assistant visual review, not two-human adjudication. Public validation data may have appeared in pretraining. No representative Camera production cohort, complete caption-truth, movie, multi-image or non-English certification.

Qwen uses explicit think=false for bounded image output. Nine failed as-is-profile cases remain separate diagnostics; the full corrected-profile cohort is used here. Other models were unchanged.

[Raw completed run](recognition-results.json), [references](recognition-manifest.json), [per-case scores](recognition-summary.json), [protocol and revisions](protocol.json). Moderation is a separate evaluation and does not change this ranking.
