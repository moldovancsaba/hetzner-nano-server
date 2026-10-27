# Independent forbidden-content screening benchmark

Scope: nine named Fanmass categories, evaluated separately from general vision, English structured tasks, non-English capability, and movies. The optional `other` catch-all is not a tenth named benchmark category.

Read [manifest](manifest.json) for reference labels, per-image notes, source and transformed-input SHA256. Read [results report](REPORT.md) for outcomes and limitations. This is an offline benchmark, not a deployed filter or an automatic rejection policy.

## Corpus and label policy

25 reviewed images: 19 images from the held-out test split of [Harmful-Contents](https://huggingface.co/datasets/onullusoy/harmful-contents), two [Twemoji](https://github.com/twitter/twemoji) gesture illustrations (CC-BY 4.0), three controlled English text/symbol fixtures, and one existing neutral COCO cats fixture. Research source images are not redistributed. Harmful-Contents states research/non-commercial use; commercial rights need independent verification. Source images, review sheets and transformed inputs remain under the owner's ignored `private/moderation-test/`; temporary server inputs are removed after the run.

Labels are a single visual review, not independently adjudicated ground truth. Broad source labels were not copied blindly. Visible guns/knives without an assault are weapons positives and violence negatives. Unknown pills, white granules, mushroom species and CBD legal status require review, not a guessed illegal-drug classification. The drug category is visible drug-related material, not a legal finding. Real guns/attack knives count; toys and paintball markers are explicit hard negatives for this benchmark. These policy choices require agreement before production use.

All nine categories have at least one positive. Sexual-content positives are explicit adult-appearing pornographic poses, not verified sexual acts. People appear adult in nudity references, but identity/age is not independently verified. No source images are published. Nonsexual nudity is a sexual-content negative. One restraint/coercion image is the only violence positive; no coverage claim for fighting or gore. Middle-finger and hate-symbol positives are illustrations; hate-word screening is English-only, separate from other-language moderation. Only one reviewer selected labels; subjective cases need adjudication.

## Model and runtime profile

- LFM2.5-VL 450M Q8 and LFM2.5-VL 1.6B Q4, one at a time.
- Hetzner CAX11, 2 ARM64 CPU, 4 GB RAM; unchanged Ollama container limit 2800 MiB.
- Native loopback `/api/generate`; max image edge 640, context 2048, batch 32, output 256, temperature zero.
- Compact schema: nine Boolean-or-null category values plus one evidence sentence. Null means review. Schema differs from Fanmass's full confidence/detail/severity output; this is not a drop-in integration test.
- Every image is presented without its label, category filename or source metadata. Labels never appear in prompts/schema. Category names are the same for all images.
- One inference per model/image, fixed order. Report cold/load timing separately from case latency. No repeatability confidence claims.
- Existing model inventory preserved; only newly fetched candidate packages removed. Qwen3 restored afterward. Other requests are not globally locked by this benchmark, so traffic may affect timing and cause switching.

## Reproduction

`run.py` is a privileged server-side benchmark runner. It requires Docker access, the existing `narimato-ollama` container and private `inputs/manifest.json` plus the exact hashed input files. It downloads candidate weights, makes bounded inference requests and removes only new packages; inspect code and server state first. Do not run the whole Fanmass application merely to reproduce this test.

Private corpus is intentionally absent from Git. Provision licensed inputs separately. The published runner has a readability-only cleanup of an equivalent request expression after execution; raw requests, prompt and settings are retained in results. Copy results back, run `python3 benchmarks/moderation/report.py`, and verify both project authentication health checks and restored chat. A failed or invalid response is a technical failure, not an absent violation. Abstentions are reported separately from false negatives. Sparse positives are a smoke test, not production recall certification.

## Integration finding from source review

At Fanmass revision `cd5be7d31b5092dad0451de3f8317f7ea0c5332a`, `services/content_moderation.py` normalizes missing category objects to `detected: false`. Deferred/unparsed outputs also contain `flagged: false`, although their status is pending/unparsed. Consumers must honor status and preserve an explicit review state; false alone must never be interpreted as moderation clearance. This benchmark's nullable schema cannot be passed straight through that normalizer. No Fanmass changes were made.

The existing image-analysis lock coordinates local processes, not all remote consumers of the Hetzner service. A production worker needs a scheduler shared with chat, bounded queue and timeouts, image-size limits, model allowlist and authenticated transport. Do not expose native model pull/delete endpoints publicly.
