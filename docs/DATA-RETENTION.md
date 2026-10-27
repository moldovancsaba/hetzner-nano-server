# Data retention, model storage and training boundary

Owner policy confirmed 2026-10-27: **retain only curated, explicitly approved datasets and labels for training; never capture live Camera images or user conversations.** This applies to the AI server, not automatic deletion of Camera's separately authorized source-photo storage.

## What stays and what goes

| Data | Retention/location | Rule |
| --- | --- | --- |
| Live image/text request bodies | Bounded gateway queue/worker RAM only | Never written to disk by this service; discard after execution, queue expiry or queued-job deletion |
| Generated answers, descriptions and moderation evidence | Gateway RAM until client deletion or five-minute terminal-result TTL | No production answer/evidence archive; no automatic training capture |
| Queued jobs | RAM, maximum 180-second wait | Fail and discard payload when waiting deadline expires |
| Running job | RAM during bounded inference | No unsafe forced cancellation; running-job DELETE returns 409 |
| Job IDs, hashes and idempotency metadata | Same transient record lifetime | Deleted with the record; no durable per-customer tracking/history |
| Browser Pandora history | Current tab memory | No database/localStorage history; new chat or reload clears it |
| Native inference/KV state | Ollama model RAM until unload/idle expiry | Not a disk archive; freeing RAM is not forensic secure erasure |
| Production request/response backups | None | Do not include transient queue data in snapshots, debug dumps or training export |
| Model discovery metadata | Restricted server registry; bounded discovery snapshots | Metadata only; snapshots 30 days/50 MiB, registry 10,000 records |
| Tested/declined model metadata and benchmark evidence | Versioned repository and approved metadata backup | Keep source, revision/digest, settings, failure, decision and scores even after weights are removed |
| Current winning weights | Ollama persistent model store | Pin every task default; keep verified digests |
| Registered alternatives / rollback weights | Reviewed model cache | Explicit pins retained; previous-winner rollback target seven days, then review use/budget |
| Declined weights | Remove after evidence capture and safety checks | Keep decline metadata and re-test condition, not the binary |
| Approved training datasets and labels | Separate access-controlled dataset store, outside public Git and request storage | Require provenance/approval/version/split/retention manifest; do not silently reuse live traffic |
| Approved adapters/training outputs | Separate artifact store with run manifest | Keep only explicitly approved artifacts; link dataset version, config, digest and holdout results |
| Credentials and private config backups | Restricted secret store | Never public Git, discovery reports or training material; separate rotation/backup rules |

## Client acknowledgement and deletion

After consuming a result, call:

```http
DELETE /v1/jobs/{id}
Authorization: Bearer <same-service-key>
```

Camera may also use `DELETE /v1/moderation/jobs/{id}` for moderation jobs. Response 200 `{"deleted":true}` removes a completed/failed job or cancels/removes queued work. Another service's ID returns 404. Running work returns 409; wait for completion, then delete. Unknown/deleted/expired IDs return 404.

Deletion removes the transient result, hashes, payload if queued, and idempotency record. Retrying the original submission afterward can create new work; do not reuse deletion as an automatic retry mechanism. API deletion does not delete a Camera source photo or an application-side copy of the result.

Without acknowledgement, terminal jobs expire after **300 seconds**. The scheduler checks expiry while idle at roughly five-second intervals as well as during requests. Clearing last-result worker references prevents the most recent answer staying reachable just because no next job arrives. Limits remain eight waiting jobs, four queued/running per service and 64 retained records. Restart loses transient data.

These are logical service-retention guarantees, not certified secure erasure of physical RAM or OS buffers. Native model KV/prompt caches are separate transient runtime state and may remain until idle unload; text currently uses the runtime's 30-minute keep-alive, vision one minute. A stricter unload-after-every-job mode would trade throughput for shorter cache residency and is tracked separately. Images/text are not intentionally written into an inference-service database or file log.

No live production body, answer, evidence sentence or input hash is persisted into discovery or model-usage records. Aggregate counts/timing/last-used metadata may be added separately without content or personal identifiers. Do not enable request-body logging, inference debug dumps or durable payload queues without a new explicit data design.

## Training and evaluation material

No production data is used for training. An approved dataset version must record:

- dataset ID/version, source/provenance and permitted purpose;
- explicit approval reference, owner and permitted users;
- license/consent restrictions, deletion/revocation/expiry handling;
- file checksums and storage location without embedded credentials or signed URLs;
- labels, rubric, annotator review and corrections;
- immutable train/validation/holdout splits and overlap checks;
- retention/review date and training runs/artifacts that used it.

Public Git can contain redacted manifests, schemas, synthetic fixtures, authorized benchmark metrics and non-sensitive decision notes. Private/restricted images, user text, credentials and raw approved training files stay in the controlled dataset store. Existing moderation research images remain research/test material under their source restrictions; they are not automatically training-approved. Do not move held-out tests into training and continue calling them unseen evaluation.

Keep run configuration, code revision, approved dataset version, adapter/model hashes, measured improvements/regressions and rejection reasons. This information supports future learning even when a model binary is deleted. No actual fine-tuning run or new training corpus was created here.

## Model-weight storage policy

Machine-readable targets are in [config/model-storage-policy.json](../config/model-storage-policy.json): 8 GiB target free space, 4 GiB hard floor, 16 GiB target weight-cache budget, all ranked defaults protected, plus explicit Qwen 0.6B/1.7B alternative pins. These targets are reviewed operating limits, not a deployed automatic LRU eviction service.

Before downloading a candidate, account for the artifact, projector/encoder and temporary copy. If projected free space crosses the hard floor, clean reviewed cache items or defer the test; never delete an active/default/pinned model to make a benchmark fit. Keep one approved candidate at a time and remove newly declined packages after recording results.

Daily discovery reports disk/inventory metadata and known decline decisions. Automatic weight deletion is disabled. `scripts/retire_declined_models.py` defaults to a dry run and removes only explicitly declined models with `--apply`, refusing current defaults, pins or loaded models. It writes a metadata audit before/after; it does not prune arbitrary installed alternatives or inference data.

Applied cleanup: Qwen3-VL 2B and Ministral 3B had failed current-environment eligibility and were not selectable for production jobs. Their weights were removed after capturing exact digests/decisions; the audit is [here](../results/retention/declined-model-cleanup.json). Free disk rose from about 6.5 GiB to about 11 GiB. Other installed alternatives remain available; use telemetry and a reviewed cache plan before removing them.

A future LRU tool must protect client-registered pins and defaults, honor rollback windows, emit a dry-run plan and preserve all test/decline metadata. Model names alone are not versions: a changed artifact or runtime can justify a reviewed re-test, never a silent reintroduction.

## Backups and verification

Back up approved metadata, policies, redacted manifests and training run records. Back up secrets separately with restricted access. Exclude production queue payloads/results, browser sessions, transient worker memory, temporary research downloads and unnecessary weight caches. Actual whole-server snapshot/backup policies have not been audited; do not claim absent snapshots merely because the application writes no request files. Off-host encrypted backup/restore testing is in the backlog.

[Live deletion verification](../results/retention/public-verification.json) checks five-minute retention reporting, owner-only deletion and disappearance of terminal text/image results. Unit tests cover queued cancellation, running-job refusal, expiry and tenant boundaries. [Backlog](../BACKLOG.md) lists client acknowledgement integration, cache statistics and strict RAM-cache privacy as remaining work.
