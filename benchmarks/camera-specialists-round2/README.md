# Marqo binary NSFW follow-up

Pinned model: `Marqo/nsfw-image-detection-384`, revision `0c26ec22111b83f106d72a55f611ec35962bcb65`. Source and resource limits are frozen in `plan.json`; same 41 public research images as the earlier specialist cohort, fixed threshold 0.5 before inference.

The source is safetensors, loaded into the standard installed timm `vit_tiny_patch16_384` implementation with strict state-dictionary matching and no model-provided code. `export.py` verifies source SHA256, exports fixed-shape ONNX, then compares logits on all 41 inputs. `export-audit.json` records numeric parity. `preprocessing-parity.json` verifies the separate server preprocessing matches the publisher's timm reference for all inputs. Important: **NSFW is label index 0**, unlike the previous two specialists. Input processing preserves aspect ratio and center-crops; it does not stretch every image to a square.

`run.py` waits for the shared gateway maintenance lease before loading, unloads the native worker and holds a renewable lease for this short run. Run under a separate systemd cgroup at 2 CPU / 2800 MiB. It saves each result atomically, restores Granite, restores cleanup, and releases the lease. Tests never count as production demand. `score.py` refuses unfinished or unrestored runs.

Binary specialist recall/false alarms are separate from the nine-category macro score. Only the union of nudity and sexual content is labelled; unknown labels remain unknown. Four positives in this set cannot establish rare-category safety or Camera customer accuracy. No live images or training collection. Human review remains required. No specialist API route is enabled by this benchmark.

## Completed — 2026-11-01

**41/41** valid binary outputs: **3/4** known positive images detected, **one false alarm among 36 negatives**, one unknown image excluded from binary accuracy. Binary F2 **0.750**; median native inference **0.1958 s**, nearest-rank p95 **0.2255 s**. Load took **0.115 s**; process peak RSS **124,812 KiB** (about 122 MiB). These are inference timings after image preprocessing, matching the earlier specialist timing method, not HTTP/end-to-end latency. The complete isolated server run took seconds after its lease wait.

This matches AdamCodd's detection/false-alarm counts on this small set, at lower observed median inference time (AdamCodd: .684 s; Falconsai: .550 s). It does not beat the historical Qwen binary detections (4/4), and four positives give a very wide recall interval, approximately **0.30–0.95**. No threshold was retuned. See [summary](summary.json), [raw results](results.json), [export parity](export-audit.json), [pixel parity](preprocessing-parity.json) and [original-versus-server parity](server-parity.json).

The updated [one/two/three-model retrospective comparison](combination-results.json) includes the new InternVL and Marqo measurements. The best six-reason macro-F2 (.8180) is tied by InternVL alone, the best pair and the best triple: the extra models add no score gain under this retrospective metric. InternVL abstains frequently, and this metric does not penalize uncertain negative cases. These are not calibrated ensemble recommendations and no fan-out API is deployed. A fresh holdout must assess coverage and review workload before adding 1–3 model routing.

Granite was restored, hourly cleanup re-enabled, and temporary ONNX/source-cache/evaluation-image copies and the standalone test environment were removed after evidence collection. The retained evaluation source images remain in the existing private approved fixture store. Marqo is not API-selectable; only its metadata, scripts and results are retained. No training data was collected.
