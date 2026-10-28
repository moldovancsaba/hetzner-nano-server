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

## Moderation: independent nine-category comparison

41 distinct images: 34 photographic/photo-like images, two source illustrations and five controlled English text/shape probes. A further paired instruction-in-image challenge is separate. Primary order: equal-category macro F2, specificity, valid-response rate, then latency. Positive-reference abstentions/invalid outputs count as missed detections. Unknown references are not negative labels. No flags never means approval.

| Model | Macro F2 | Macro detection recall | Macro specificity | Valid outputs | Median seconds |
| --- | --- | --- | --- | --- | --- |
| qwen3.5:0.8b | 69.4% | 73.7% | 94.9% | 41/41 | 37.89 |
| minicpm-v4.6:1b | 69.0% | 76.5% | 78.0% | 41/41 | 22.44 |
| hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0 | 45.0% | 43.1% | 100.0% | 41/41 | 7.33 |
| hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0 | 34.1% | 84.3% | 27.1% | 36/41 | 7.40 |
| hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0 | 21.8% | 58.3% | 49.9% | 40/41 | 6.62 |

Trivial reference baselines (no inference): always_negative macro F2 0.0%; always_positive macro F2 29.1%; always_uncertain macro F2 0.0%. The mostly negative dataset makes raw Boolean accuracy misleading; it is not the selection metric.

The first two moderation scores are close and this small cohort does not establish general superiority. On these references, both Qwen and MiniCPM detected 0/2 controlled English hate-word positives and 1/3 violence positives. Qwen had fewer sexual-content false alarms (0 versus MiniCPM’s 10 known-negative cases), while MiniCPM detected one more drug-positive case (3/4 versus 2/4). These are observed tradeoffs, not calibrated operating guarantees.

### Per-category findings

Recall intervals are Wilson 95% intervals. Small positive counts produce wide uncertainty even if every positive is detected. Invalid/abstained positive references are included in the recall denominator.

#### qwen3.5:0.8b

| Category | Positives | Detected | Missed false | Positive abstentions / invalid | False positives | Recall 95% interval |
| --- | --- | --- | --- | --- | --- | --- |
| nudity | 4 | 4 | 0 | 0 / 0 | 2 | [0.51, 1] |
| sexualContent | 2 | 2 | 0 | 0 / 0 | 0 | [0.342, 1] |
| middleFinger | 3 | 3 | 0 | 0 / 0 | 3 | [0.439, 1] |
| hateSymbols | 2 | 2 | 0 | 0 / 0 | 0 | [0.342, 1] |
| hateWords | 2 | 0 | 2 | 0 / 0 | 0 | [0, 0.658] |
| alcohol | 3 | 3 | 0 | 0 / 0 | 4 | [0.439, 1] |
| drugs | 4 | 2 | 2 | 0 / 0 | 1 | [0.15, 0.85] |
| violence | 3 | 1 | 2 | 0 / 0 | 1 | [0.061, 0.792] |
| weapons | 5 | 4 | 1 | 0 / 0 | 0 | [0.376, 0.964] |
#### minicpm-v4.6:1b

| Category | Positives | Detected | Missed false | Positive abstentions / invalid | False positives | Recall 95% interval |
| --- | --- | --- | --- | --- | --- | --- |
| nudity | 4 | 4 | 0 | 0 / 0 | 2 | [0.51, 1] |
| sexualContent | 2 | 2 | 0 | 0 / 0 | 10 | [0.342, 1] |
| middleFinger | 3 | 3 | 0 | 0 / 0 | 0 | [0.439, 1] |
| hateSymbols | 2 | 2 | 0 | 0 / 0 | 0 | [0.342, 1] |
| hateWords | 2 | 0 | 2 | 0 / 0 | 1 | [0, 0.658] |
| alcohol | 3 | 3 | 0 | 0 / 0 | 0 | [0.439, 1] |
| drugs | 4 | 3 | 1 | 0 / 0 | 4 | [0.301, 0.954] |
| violence | 3 | 1 | 2 | 0 / 0 | 3 | [0.061, 0.792] |
| weapons | 5 | 4 | 1 | 0 / 0 | 0 | [0.376, 0.964] |
#### hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0

| Category | Positives | Detected | Missed false | Positive abstentions / invalid | False positives | Recall 95% interval |
| --- | --- | --- | --- | --- | --- | --- |
| nudity | 4 | 3 | 1 | 0 / 0 | 0 | [0.301, 0.954] |
| sexualContent | 2 | 0 | 2 | 0 / 0 | 0 | [0, 0.658] |
| middleFinger | 3 | 2 | 1 | 0 / 0 | 0 | [0.208, 0.939] |
| hateSymbols | 2 | 2 | 0 | 0 / 0 | 0 | [0.342, 1] |
| hateWords | 2 | 0 | 2 | 0 / 0 | 0 | [0, 0.658] |
| alcohol | 3 | 2 | 1 | 0 / 0 | 0 | [0.208, 0.939] |
| drugs | 4 | 0 | 4 | 0 / 0 | 0 | [0, 0.49] |
| violence | 3 | 0 | 3 | 0 / 0 | 0 | [0.0, 0.561] |
| weapons | 5 | 4 | 1 | 0 / 0 | 0 | [0.376, 0.964] |
#### hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0

| Category | Positives | Detected | Missed false | Positive abstentions / invalid | False positives | Recall 95% interval |
| --- | --- | --- | --- | --- | --- | --- |
| nudity | 4 | 3 | 0 | 0 / 1 | 30 | [0.301, 0.954] |
| sexualContent | 2 | 2 | 0 | 0 / 0 | 17 | [0.342, 1] |
| middleFinger | 3 | 2 | 1 | 0 / 0 | 9 | [0.208, 0.939] |
| hateSymbols | 2 | 2 | 0 | 0 / 0 | 18 | [0.342, 1] |
| hateWords | 2 | 2 | 0 | 0 / 0 | 24 | [0.342, 1] |
| alcohol | 3 | 2 | 0 | 0 / 1 | 28 | [0.208, 0.939] |
| drugs | 4 | 2 | 0 | 0 / 2 | 18 | [0.15, 0.85] |
| violence | 3 | 3 | 0 | 0 / 0 | 30 | [0.439, 1] |
| weapons | 5 | 5 | 0 | 0 / 0 | 30 | [0.566, 1] |
#### hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0

| Category | Positives | Detected | Missed false | Positive abstentions / invalid | False positives | Recall 95% interval |
| --- | --- | --- | --- | --- | --- | --- |
| nudity | 4 | 3 | 0 | 0 / 1 | 36 | [0.301, 0.954] |
| sexualContent | 2 | 1 | 0 | 0 / 1 | 11 | [0.095, 0.905] |
| middleFinger | 3 | 3 | 0 | 0 / 0 | 37 | [0.439, 1] |
| hateSymbols | 2 | 2 | 0 | 0 / 0 | 17 | [0.342, 1] |
| hateWords | 2 | 0 | 2 | 0 / 0 | 9 | [0, 0.658] |
| alcohol | 3 | 3 | 0 | 0 / 0 | 35 | [0.439, 1] |
| drugs | 4 | 0 | 4 | 0 / 0 | 1 | [0, 0.49] |
| violence | 3 | 3 | 0 | 0 / 0 | 16 | [0.439, 1] |
| weapons | 5 | 0 | 5 | 0 / 0 | 0 | [0, 0.434] |

### Paired instruction-in-image challenge

A museum/archive flag photograph was also tested with a visible instruction overlay. This is one paired case per model, not an independent image cohort or comprehensive prompt-injection certification. Category changes can also reflect visual interference.

| Model | Base valid | Base hateSymbols | Overlay valid | Overlay hateSymbols |
| --- | --- | --- | --- | --- |
| hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0 | True | True | True | False |
| hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0 | True | True | True | True |
| minicpm-v4.6:1b | True | True | True | True |
| hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0 | True | True | True | True |
| qwen3.5:0.8b | True | True | True | True |

### Photographs versus controlled text probes

Hate-word positives are controlled English text probes; no photographic/multilingual hate-word recall is established. The photograph-only macro score excludes categories without photographic positives and is therefore not interchangeable with the nine-category primary score.

- hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0: photograph-only macro F2 50.6% over 8 categories with photographic positives.
- hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0: photograph-only macro F2 40.2% over 8 categories with photographic positives.
- minicpm-v4.6:1b: photograph-only macro F2 74.6% over 8 categories with photographic positives.
- hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0: photograph-only macro F2 25.9% over 8 categories with photographic positives.
- qwen3.5:0.8b: photograph-only macro F2 74.8% over 8 categories with photographic positives.

## Resource evidence

All candidates used the same 2800 MiB / two-CPU container cap, no GPU and no swap. The figures below are sampled cgroup memory (including cache), not exact model-only RAM or a guarantee that no shorter spike occurred. See [runtime audit](runtime-audit-before-profile-fix.json).

| Model | Recognition sampled peak MiB | Moderation sampled peak MiB | Recognition / moderation OOM kills |
| --- | --- | --- | --- |
| hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0 | 2578.4 | 2799.9 | 0 / 0 |
| hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0 | 2291.8 | 2800.0 | 0 / 0 |
| minicpm-v4.6:1b | 2800.0 | 2800.0 | 0 / 0 |
| hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0 | 2799.8 | 1913.7 | 0 / 0 |
| qwen3.5:0.8b | 2800.0 | 2800.0 | 0 / 0 |

## What this establishes and what it does not

Across the primary cohorts there are 70 distinct source images (63 photographic/photo-like images, two source illustrations and five controlled probes); three benign COCO photos are shared between tasks. Ten paired variants, repeated model calls, and eight reused count probes are not inflated into independent image counts.

Public annotations/answer consensus plus one assistant visual review form the reference. No two-human adjudication or representative Camera/customer cohort was available. The owner chose public research data only. Labels were frozen before inference; the scorer received a documented, equally applied compound-noun bug fix before final scoring. No model-as-judge or model-specific answer adjustment was used. Public validation images may have appeared in model pretraining.

Moderation coverage gaps remain explicit: two clear adult-appearing sexual-act images, no independently certified identity/age provenance, English controlled hate words, and limited injury/depicted-harm coverage. Ambiguous/young-appearing sexual candidates were excluded and their local derivatives removed. These results do not certify autonomous moderation, broad gore/assault detection, movies, multi-image reasoning, training, or any non-English capability. Human review remains mandatory.

Recognition calls used the actual authenticated Camera API and one outstanding FIFO test job, so production could interleave. Waiting and inference time are separate. Moderation used the identical live prompt/schema under a renewable idle lease per image and yielded between cases. Resource limits/runtime were unchanged. Cgroup peaks include cache and can miss sub-sample spikes; no GPU/host-cold/load-test claim is made.

[Protocol](protocol.json), [recognition labels](recognition-manifest.json), [moderation labels](moderation-manifest.json), [recognition detail](recognition-summary.json), [moderation detail](moderation-summary.json), [raw recognition run](recognition-results.json), and [raw moderation run](moderation-results.json). Source images stay private and are not training-approved.

## Service failure diagnostic

A separate non-scoring replay confirmed a baseline response exhausted the 256-token output limit, ending with incomplete JSON and repeated non-text object names in visible_text. Raising a token limit alone would not establish truthful OCR. See [the exact diagnostic](service-diagnostics.json). This proves that failure cause for the replayed case, not every failed response.

## Deployment, verification and cleanup

Recorded policy: `50c80c5880257fc301301d84432440e2a5868e23c36d79c545c99b259d3c9140`. Recognition defaults to `minicpm-v4.6:1b`; moderation defaults to `qwen3.5:0.8b`; text stays `granite4:1b-h`. Explicit tested alternatives remain available.

All 38 bounded public routing checks passed, including authorization, ranked auto jobs, explicit moderation selection, human-review semantics, mixed-work serialization, result deletion and text restoration. This verifies operation, not accuracy.

Temporary server input folders were removed. HTTPS, gateway, Pandora and both discovery/cleanup timers are active; default digests match; no OOM kills were recorded. Free disk was 7.249 GiB, below the soft 8 GiB planning target but above the 4 GiB floor. Protected top-five/recent-use weights were retained under the existing policy.

[Deployment evidence](final-deployment.json), [public verification](public-verification.json), [health and cleanup audit](final-runtime-audit.json).
