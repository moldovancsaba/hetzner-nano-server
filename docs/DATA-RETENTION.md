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
| Other installed model weights | Automatic hourly retention | Keep top five per job or admitted non-test demand within 14 days; initial history grace and active-work safeguards apply |
| Declined weights | Remove after evidence capture and safety checks | Keep decline metadata and re-test condition, not the binary |
| Approved training datasets and labels | Separate access-controlled dataset store, outside public Git and request storage | Require provenance/approval/version/split/retention manifest; do not silently reuse live traffic |
| Approved adapters/training outputs | Separate artifact store with run manifest | Keep only explicitly approved artifacts; link dataset version, config, digest and holdout results |
| Credentials and private config backups | Restricted secret store | Never public Git, discovery reports or training material; separate rotation/backup rules |

## Operational metadata

Owner-authorized usage reporting now stores project/task/model identifiers, test/production purpose, normalized route/status/error codes and timings for 30 days, capped at 200,000 events and a 64 MiB database-page ceiling. It contains no payloads, answers, image hashes, job IDs, idempotency keys, IPs, raw URLs or credentials. This is separate from the model-retention ledger and training material. See [reporting and alert details](OBSERVABILITY.md). Email was explicitly deferred; in-chat alerts and the two host watchdogs are active.

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

The owner’s current rule is implemented by the [automatic model cleaner](AUTO-MODEL-CLEANUP.md): keep top five **per task** plus models selected by admitted non-test inference requests during the last 14 days. This supersedes permanent alternative pins and the previous seven-day rollback target. Existing weights have one initial 14-day history grace because past non-test use was not tracked. Defaults, resident models and queued/running work are protected. Cleanup runs hourly with up to five minutes jitter and no public model-install endpoint.

`config/model-storage-policy.json` records this policy. The 8 GiB target free space, 4 GiB hard download floor and 16 GiB target cache budget remain capacity-planning targets, not permission to delete recently used/protected models. If protected weights exceed budget, defer new downloads and review capacity rather than breaking retention rules.

Production-use metadata now persists separately: model name, digest, aggregate admitted production-request count and last timestamp only. No content, identity or per-request payload is stored. Tests must send `X-Request-Purpose: test`; repository verification/benchmark helpers do so. Health checks, polling and discovery never extend retention. Unmarked inference counts as production; the server does not inspect content to guess whether it is a test.

Daily discovery continues to report disk/inventory metadata; it does not delete weights itself. The separate privileged cleaner acquires an idle gateway maintenance lease, writes metadata decisions before deleting, rechecks eligibility and releases the lease. It fails closed if trustworthy policy/usage/lease data is unavailable. Approved training/evaluation data and all historical model evidence are outside the cleaner’s deletion scope.

Historical cleanup removed Qwen3-VL 2B and Ministral 3B after their eligibility failures; the [original audit](../results/retention/declined-model-cleanup.json) remains. The old retire-declined helper now refuses deletion under policy v2. The hourly cleaner owns removal decisions. Pause the cleanup timer before native benchmark experiments and re-enable it after restoring production; unranked temporary downloads otherwise have no production-use protection.

## Backups and verification

Back up approved metadata, policies, redacted manifests and training run records. Back up secrets separately with restricted access. Exclude production queue payloads/results, browser sessions, transient worker memory, temporary research downloads and unnecessary weight caches. Actual whole-server snapshot/backup policies have not been audited; do not claim absent snapshots merely because the application writes no request files. Off-host encrypted backup/restore testing is in the backlog.

[Live deletion verification](../results/retention/public-verification.json) checks five-minute retention reporting, owner-only deletion and disappearance of terminal text/image results. Unit tests cover queued cancellation, running-job refusal, expiry and tenant boundaries. [Backlog](../BACKLOG.md) lists client acknowledgement integration, cache statistics and strict RAM-cache privacy as remaining work.
