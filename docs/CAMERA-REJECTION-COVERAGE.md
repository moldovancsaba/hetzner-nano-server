# Camera rejection-reason coverage and model combinations

Human approval is always required. Analysis supplies reviewer hints; it never approves, rejects, publishes or changes a Camera submission. An all-negative result is not clearance.

## Camera requirements and the current API differ

Verified against Camera `origin/main` revision `95845c98` on 2026-10-28: `lib/photo-vetting/vocabulary.ts` defines twelve standard rejection reasons, with general/partner/event vocabulary overrides. These are selectable policy reasons, not universal prohibitions at every event. Resolve the actual event vocabulary and rules in Camera; the inference server has no access to Camera's database.

The existing `image_moderation` API has **nine signals**, not twelve Camera reasons. Its stable schema remains unchanged. The mapping below is application-side guidance, not newly deployed API fields.

| Camera reason | Existing API signals / required capability | Current coverage |
| --- | --- | --- |
| `nudity` — nudity or sexual content | `nudity` OR `sexualContent`; a binary NSFW specialist can assist this combined reason | Measured on a small research set; no broad explicit-sex certification |
| `offensive_gesture` | `middleFinger` | Only middle finger tested; other offensive gestures unverified |
| `alcohol` | `alcohol` | Small research evaluation; container ambiguity remains |
| `violence` — violence or weapons | `violence` OR `weapons` | Small research evaluation; both kinds need separate error reporting |
| `hate` — hate symbol or offensive text | `hateSymbols` OR `hateWords` | English hate words only; current models miss the controlled word positives; no Hungarian-text approval |
| `drugs` — drugs or smoking | `drugs` | Existing drug/paraphernalia rubric does not establish full smoking/vaping coverage |
| `competitor_brand` | Brand/logo detection + OCR + event-specific prohibited-brand list | Not supported by moderation v1; recognition can provide unverified evidence only |
| `political` | OCR/symbol evidence + explicit event rule | Not supported or evaluated; do not infer a person's beliefs |
| `forbidden` | Explicit additional event rule | No generic v1 catch-all; require human interpretation |
| `poor_quality` | Blur/exposure checks + face presence, independently evaluated | Not provided by moderation v1; a visible person is not proof of a usable face |
| `spam_test` | Selfie/content classification plus application context | Not supported; an image alone does not establish spam or intent |
| `other` | Reviewer explanation | Manual reason; no objective universal detector |

## Preserve uncertainty

For a mapped reason, flag it when any mapped signal is `detected`. Use `not_detected` only when every mapped signal is `not_detected`; otherwise use `uncertain`. For unsupported reasons use `not_evaluated`, never `not_detected`. Unsupported reasons must not disappear into an all-clear summary. Missing, invalid and truncated outputs remain unavailable.

A binary NSFW score is one signal for the combined nudity/sexual-content reason. It cannot determine which subtype is present, age, consent, legality or the other eleven Camera reasons. Do not present its score as a calibrated confidence percentage.

## Compare one, two and three components

The first follow-up evaluates pinned Falconsai and AdamCodd NSFW classifiers on all 41 existing frozen public research images, CPU-only on Hetzner, at a fixed predeclared 0.5 threshold. Images are not live uploads and are not training data. Standard preprocessing and export parity are checked; resource and timing evidence are recorded separately from Ollama. These classifiers require an ONNX runtime adapter and are **not callable production models in `/v1/models`** merely because they were tested.

[Specialist results and combination analysis](../benchmarks/camera-specialists/REPORT.md) compare historical general-model outputs and new specialist outputs. Alert unions are exploratory: choosing a combination on these same images requires fresh held-out validation before promotion. Per-reason recall and false alarms matter more than a single aggregate score. A third model should earn its memory, switching and latency costs through additional useful detections, not just duplicate existing flags.

A practical architecture to evaluate is:

1. One general moderation model for broad signals.
2. At most one specialist when it adds measured detection value, rather than two redundant NSFW classifiers.
3. A complementary OCR/object/quality component for demonstrated remaining gaps. Test named logos, smoking/vaping, gestures, Hungarian text and image quality with explicit event rules before advertising coverage.

Deterministic blur/exposure checks need not consume an LLM slot. A broad VLM + NSFW classifier + OCR/quality component is a candidate design, not a claim that all twelve reasons are solved. Models are loaded sequentially under the shared resource budget; do not keep three inference engines resident on the 4 GB host.

## Measured follow-up decision

The new specialists completed all 41 images each: Falconsai detected 2/4 positive nudity/sexual-content references, AdamCodd 3/4, versus the historical Qwen baseline’s 4/4, each with one false flag among 36 defined negatives. Neither added a positive to Qwen. Keep one broad default today; the useful two-model follow-up is Qwen + LFM2.5-VL 450M Q8, which adds one violence/weapon detection without extra false flags in the six-reason retrospective analysis. The best three-model F2 ties the best pair: no third model earns deployment from this evidence. Fresh validation and remaining-reason fixtures are required.

## Calling what exists today

Use the dedicated Camera key and submit `task: image_moderation`, `model: auto` through `/v1/jobs` or the existing moderation routes. Poll, consume and DELETE each result. Synthetic checks send `X-Request-Purpose: test`. Preserve source-revision checks and manual review even after success.

For optional object/text observations, submit a separate `image_recognition` job with `model: auto`; it uses a different ranking. That result is not a moderation judgment and has not been validated for branded competitor or political-policy matching. There is no deployed twelve-reason ensemble endpoint, automatic multi-model fan-out or specialist routing contract in this release. Do not send undocumented task names or expect automatic retries to run another model.

Keep request images and answers transient. Never collect live Camera images for future tests or training. Retain aggregate test evidence, artifact revisions, decisions and failure reasons after declining/removing weights.
