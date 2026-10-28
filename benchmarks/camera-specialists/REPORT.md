# Camera specialists and 1–3-model combinations — 2026-10-28

**Human approval always remains authoritative. No new classifier or ensemble is deployed through the public API.** Two new specialists completed 82 image analyses on the actual Hetzner CPU server. Neither added a new positive detection to the current Qwen moderation baseline on this small set.

## New specialist measurements

The exact same 41 frozen public research images were used, with verified SHA-256 hashes and existing labels. For a binary NSFW classifier the reference is the union of `nudity` and `sexualContent`: four positive, 36 negative, one ambiguous/excluded reference. No binary classifier result establishes which sexual-content subtype is present or coverage of any other Camera reason. The fixed threshold was 0.5 before inference; scores are not calibrated probabilities.

| Model / actual artifact | Positive detections | Misses | False flags among 36 negatives | Median warm CPU inference |
| --- | --- | --- | --- | --- |
| Falconsai NSFW, pinned FP32 ONNX export | 2/4 | 2 | 1 | 0.550 s |
| AdamCodd ViT NSFW, pinned quantized ONNX | 3/4 | 1 | 1 | 0.684 s |
| Historical Qwen3.5 0.8B moderation baseline, mapped union | 4/4 | 0 | 1 | See original nine-category report |

All 41 outputs per specialist were valid. Four positives are far too few to claim representative accuracy or superiority; broad explicit-sex scenarios were not certified by the original dataset. These are research comparisons, not customer-upload evaluation or training. NSFW confidence scores must not be shown as calibrated risk percentages.

Falconsai export parity was verified against the pinned standard Transformers implementation on two synthetic images: maximum logit error below 0.000005 and identical preprocessor tensors. AdamCodd uses the author's pinned `onnx/model_quantized.onnx` with its shipped processor. Both use the normal 0/1 label order verified in source configs. Different resolutions/quantizations are part of their measured profiles, not controlled architecture-only comparisons.

Measured on Hetzner CAX11 ARM64, CPU only, ONNX Runtime CPU provider, two intra-op threads, sequential sessions, separate evaluation cgroup capped at 2800 MiB and two CPU equivalents. No concurrent Ollama generation: an idle gateway lease was acquired per bounded image and resident Ollama models unloaded. Timings exclude model load, image preparation, lease/queue waiting and HTTP transport. The results include load time and peak process RSS; a sampled evaluation cgroup peak during the run was ~0.89 GiB with zero OOM events at that sample. Both models completed, Granite was restored and the cleanup timer resumed. No host inference cap was raised.

## Comparing combinations against Camera reasons

The legacy nine signals map to six of Camera's twelve standard reasons: nudity/sexual content, offensive gesture (middle finger only), alcohol, violence/weapons, hate symbol/offensive text (English word test only), and drugs (not complete smoking/vaping coverage). The other six reasons are not evaluated. This coarser six-reason analysis is distinct from the authoritative nine-category moderation ranking and does not replace it.

`compare.py` evaluates all 63 possible selections of one, two or three models from five historical general models and two newly measured specialists. A concern is flagged if any model flags it. All negatives are required for `not_detected`; unknowns remain unknown. Positive abstentions count as missed detections. Unknown reference labels are excluded, never treated as negatives. Historical model outputs are reused, not freshly remeasured under the ONNX runtime.

| Exploratory combination | Six-reason macro F2 | True reason-image detections | False reason-image flags | Interpretation |
| --- | --- | --- | --- | --- |
| Qwen3.5 0.8B, current nine-signal default | 0.719 | 19 | 10 | Keep as current broad baseline |
| Qwen + LFM2.5-VL 450M Q8 | 0.738 | 20 | 10 | One additional violence/weapon detection; useful pair for fresh validation |
| MiniCPM-V4.6 1B, historical Q4 artifact | 0.751 | 20 | 16 | Best one-model F2 in this coarser analysis, but more false alarms |
| MiniCPM + LFM2.5-VL 450M Q8 | 0.769 | 21 | 16 | Best two-model F2; false-alarm tradeoff remains |
| Best three-model F2 selection | 0.769 | 21 | 16 | Tied with the best pair; third specialist brings no additional positive detection |

Counts are category-image pairs, not distinct photos. Full per-reason counts and every combination are in `combination-results.json`. Selecting a combination on the same evaluation set is exploratory and requires **fresh held-out validation**, not automatic production promotion. The two new binary specialists are not independently capable of the remaining Camera reasons; their lower total task coverage must not be hidden by comparing binary F2 to a nine-category score.

## Recommendation by component count

1. **One model today:** keep `image_moderation`, `model: auto`, currently Qwen3.5 0.8B under the existing independent nine-category ranking. Preserve all human review and uncertain outcomes.
2. **Two-model trial:** Qwen plus `hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0`, sequentially, is the useful lower-false-alarm follow-up from these results. It adds one concern without extra false flags in this small retrospective mapping. Compare with MiniCPM + LFM if recall is prioritized over reviewer workload. No combined latency or live-client benefit has been established.
3. **Three components later:** do not add a second or redundant NSFW classifier just to fill a slot. Evaluate an OCR/logo/gesture component or independently tested quality checks against actual remaining requirements. Existing results do not identify three models that cover all twelve reasons. Blurriness/exposure may use deterministic checks without another LLM; brand/political/other bans require event rules.

## API and retention outcome

No deployed endpoint automatically fans out to multiple models. The two-model trial requires two explicit moderation jobs with the Camera key, independently polled/deleted, mapped and combined by the calling application. It must not bypass source-revision checks, result expiry or human approval. The NSFW classifiers use a different runtime and are **not new selectable IDs in `/v1/models`**. Weights from these experiments are removed from the server after collecting evidence; results, revisions, decisions and export checks remain versioned. All defaults and the shared FIFO remain unchanged.

[Full twelve-reason API coverage guide](../../docs/CAMERA-REJECTION-COVERAGE.md) · [Current moderation API](../../docs/CAMERA-MODERATION.md) · [Original nine-category evidence](../vision-evaluation/REPORT.md).

## Reproduce

Run `prepare.py` locally against the approved private research-image copy; never substitute live Camera uploads. Export/verify Falconsai with the standard pinned Transformers ViT implementation, `export_falconsai.py` and `verify_export.py`. Stage only this round's plan, manifest, runner, private images and model/processor artifacts in `/opt/narimato-benchmarks/camera-specialists`. The runner needs an isolated ONNX Runtime/Pillow/NumPy environment, an idle gateway maintenance lease and paused cleanup. Run under the recorded CPU/memory cap, restore service, copy metadata-only results back, remove temporary weights/images, then run `compare.py`. Do not retain research images for training or publish them in Git.
