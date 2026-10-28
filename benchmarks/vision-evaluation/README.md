# Broader image and moderation evaluation

Status: evaluation in progress, 28 October 2026. The earlier two-image round is a screening experiment, not a general Camera accuracy benchmark.

## Frozen design

- Recognition: 24 varied COCO 2017 validation photographs and eight TextVQA validation photographs. Published annotations/answer consensus were visually reviewed before candidate inference.
- Nine paired recognition robustness variants: dimmed/compressed versions of four base images, plus an instruction overlaid on a benign photograph. These are not nine independent new examples.
- Eight separate counting probes reuse clearly countable base images. They do not change the real service-contract score.
- Moderation: 41 distinct images, including 34 photographic/photo-like images, two source illustrations and five controlled English text/shape probes. All nine category references are Boolean or genuinely uncertain. A paired instruction-in-image challenge is separate.
- Three benign COCO photos appear in both workstreams. Across primary cohorts there are **70 distinct images: 63 photographic/photo-like images, two source illustrations and five controlled probes**, plus ten paired variants. Counts, repeated model calls and cross-task reuse are not inflated into independent sample counts.

Five working model artifacts are tested: LFM2-VL 450M Q8, LFM2.5-VL 450M Q8, MiniCPM-V 4.6 1B, LFM2.5-VL 450M Extract Q8 and Qwen3.5 0.8B. LFM3 and d1 compatibility failures remain documented in round 4; unchanged failed runtime/endpoint combinations are not retried.

## What is scored

The recognition primary test uses the **actual Camera API**, including its real prompt, schema, 640-pixel normalization, 2048 context, 256 output-token limit and error handling. One outstanding test job uses the normal FIFO queue. Queue waiting and inference wall time are recorded separately. Invalid/failed service responses receive zero credit, rather than disappearing from the denominator.

The primary recognition score is 65% mean reference-supported object F1 across the 24 COCO images and 35% target-text recall across the eight OCR images. A frozen alias dictionary accepts ordinary equivalent terms such as tabby cat/cat and sofa/couch. Source annotations plus visual review define required/allowed coarse labels; unsupported labels are reference-unsupported predictions, not a claim that every unannotated detail is hallucinated. Full free-form caption truth is not automatically graded. Counting and robustness remain separately visible.

Moderation uses the live versioned prompt/schema under a renewable idle maintenance lease, one image at a time, yielding between images so production can run. The primary metric is equal-category macro F2: positive-reference abstentions and invalid outputs count as missed detections. Unknown references are neither safe negatives nor known positives. Report false positives, specificity, abstentions, uncertainty and per-category Wilson recall intervals separately. All-null outputs cannot win through apparent negative accuracy.

Labels, protocol, scorer source, settings, digests, failures and per-case evidence are retained. No model-as-judge scoring is used. A single assistant performed the additional blinded visual reference review; no claim of two independent human adjudicators is made. Public validation datasets may have appeared in model pretraining. English text/OCR is not evidence of other-language moderation or OCR.

## Data and limits

The owner selected public research datasets for this evaluation. Live Camera/customer images and conversations are never used. Private images, source downloads and contact sheets stay under ignored `private/vision-evaluation`; no source photos are published to GitHub or approved for training. Temporary server images are removed after testing.

COCO sources retain per-image Flickr licenses and source links; TextVQA/OpenImages references retain attribution. Harmful-Contents states research/noncommercial use; this does not establish commercial image rights. Wikimedia files retain their individual attribution/licenses.

Sexual-content positives remain sparse, with two clear adult-appearing act images. Identity/age is not independently certified; ambiguous/young-appearing sexual candidates were excluded and their local derivatives removed. Hate-word positives are controlled English text probes, not a photographic or multilingual hate-speech corpus. Violence covers bruising and depicted harm, not broad graphic-assault/gore accuracy. These limits prevent production-safety certification even after a complete comparative run. Human review remains required.

This evaluation does not test movies, multi-image reasoning, training, or non-English capability.

## Reproduction and completion

Read repository AGENTS.md, CONTINUOUS-EVALUATION.md, DATA-RETENTION.md and MODEL-POLICY.md first. Preparation scripts require public source annotations and Pillow; private images are intentionally absent from a clone. Do not substitute live uploads or use reference labels in model prompts.

`recognition-manifest.json` and `moderation-manifest.json` freeze case IDs, source references, input hashes, labels and review notes. `protocol.json` records metric definitions and source hashes. `test_scoring.py` guards semantic equivalence, wrong-answer preservation, invalid-response handling and abstention accounting.

Server runners keep normal inference serialized, mark API requests as tests, pause automatic model cleanup during temporary experiments, record resource counters and restore default text afterward. Moderation waits for recognition to finish. On interruption, inspect native state before releasing maintenance or restarting anything; verify queue health and the cleanup timer.

The run is not complete until results are reviewed, separate rankings rebuilt, matching default artifacts deployed, actual auto/explicit API jobs verified, unneeded temporary weights cleaned under retention policy, inputs removed, and documentation published. Historical screening variants must not be mixed numerically into the new broader ranking; preserve their evidence and explicit-selection status separately.

A separate non-scoring native diagnostic confirmed one baseline failure hit the 256-token limit with incomplete JSON and repeated invented visible_text entries. This is evidence for that case, not a diagnosis of every failure. The ranking experiment continues unchanged.

Before any moderation inference, full-resolution review corrected one scene label and added a public-domain nonsexual classical-sculpture contrast. The initial manifest remains in Git history; protocol.json records the amendment and hashes. No model outputs drove the correction.

The as-is Qwen profile consumed its response budget on reasoning. A native diagnostic retained only reasoning length (never reasoning content). The operator added an explicit think=false vision profile, verified a real API response, preserved nine failed-profile diagnostic cases separately, and restarted Qwen on the entire cohort. The other four completed models are unchanged. Profile-control regression tests and checkpoint/resume handling were added; labels and score weights were not tuned to Qwen answers.
