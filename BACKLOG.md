# Hetzner model research and data-management backlog

Owner: platform operator. Updated 2026-10-27. This is the repository's task backlog; [the operating plan](docs/CONTINUOUS-EVALUATION.md) defines execution and [retention policy](docs/DATA-RETENTION.md) defines data boundaries.

## Delivered

| ID | Priority | Item | Acceptance evidence |
| --- | --- | --- | --- |
| MR-01 | P0 | Daily server-side metadata discovery | Enabled systemd timer, 03:30–03:45 Europe/Budapest; first run fetched all 12 feeds successfully |
| MR-02 | P0 | Preserve tested/declined model information | 28 attempted variants indexed; failure sources, decisions and removed artifact digests versioned |
| MR-03 | P0 | Separate discovery from inference | Collector performs metadata-only reads; no weight installation, inference, customer-request access or default changes |
| MD-01 | P0 | Ranking-based defaults and installed alternatives | Existing model policy, API discovery, exact-digest gates and shared queue |
| DR-01 | P0 | Remove declined weights, retain evidence | Qwen3-VL 2B and Ministral 3B removed; metadata audit retained; about 11 GiB free afterward |
| DR-02 | P0 | Minimize transient job data | Five-minute memory result TTL, active periodic expiry and authenticated DELETE acknowledgement for result/queued-job removal |
| TR-01 | P0 | Define training boundary | Owner approved curated, explicitly approved datasets and labels only; never capture live Camera inputs or conversations |

## Ready / next

| ID | Priority | Work | Definition of done |
| --- | --- | --- | --- |
| MR-04 | P1 | Review the initial shortlist and choose at most two candidates | Verify publisher, license, precise artifact/quantization/projector size, ARM64/runtime compatibility, changed condition versus prior attempts, intended task and test budget |
| EV-01 | P1 | Build approved unseen project holdouts | Versioned manifests, provenance/approval and labels; English structured tasks, general images and each moderation category scored separately; no training contamination |
| EV-02 | P1 | Standardize maintenance-window benchmark runner | Drain public queue, isolate native testing, pin resource limits, capture real peaks/OOM/load/switch times, enforce download/time/disk limits, restore and verify all services |
| EV-03 | P1 | Expand moderation validation | Enough positive, negative and ambiguous examples per category, independent label review, explicit-act/photographic gesture/hate-symbol/violence coverage gaps addressed; never auto-clear images |
| ST-01 | P1 | Add content-free per-model usage statistics | Only model/task/count/last-used/timing buckets; no text, images, user IDs, evidence sentences or input hashes; use it to review the alternative-weight cache |
| OP-01 | P1 | Add meaningful failure notification | Alert only on repeated source failures, timer failure, low disk or benchmark restore failure; choose/authorize a destination before sending external messages |
| CL-01 | P1 | Integrate result acknowledgement in clients | Camera/ClassScout poll, consume and DELETE terminal results; preserve source revision and manual-review behavior; update client contracts in their own repositories |

## Planned

| ID | Priority | Work | Definition of done |
| --- | --- | --- | --- |
| MR-05 | P2 | Improve artifact-family identity and revision matching | Distinguish architecture, base model, fine-tune, quantization, encoder/projector and revision; changed artifact/runtime triggers reviewed retest, not repetitive unchanged tests |
| EV-04 | P2 | Use weekly review and fortnightly approved test windows | Operator checklist followed; no unattended benchmark/generation schedule added until queue isolation and recovery are proven |
| ST-02 | P2 | Manage alternatives by measured use and budget | Protect all current defaults, registered client pins and rollback period; dry-run eviction report; remove only reviewed expired/unused weights, preserve metadata |
| TR-02 | P2 | Create an approved dataset/training registry | Each version has provenance, permissions, approval, split, labels, checksum, retention/revocation and access controls; raw files outside public Git and inference request storage |
| TR-03 | P2 | Plan actual training separately | Off-server compute/storage/run manifests, approved dataset version, adapter/weight provenance, holdout evaluation and rollback; never train on the production queue |
| OP-02 | P2 | Test metadata/config backup and restore | Encrypted off-host backup of approved metadata/config manifests and separately protected secrets; exclude transient requests and job results |
| DR-03 | P2 | Assess strict RAM-cache privacy mode | Measure shorter model keep-alive/unload-after-job tradeoff; document that ordinary memory freeing is not forensic secure erasure |
| OP-03 | P2 | Consider durable queue only if needed | Explicit privacy/storage design and deletion semantics before persisting any customer payload; current queue stays memory-only |

## Decision rules

A model progresses through discovered → needs_review → ready_to_test → testing → accepted / declined / deferred. Reconsider a declined model only with a recorded changed artifact, runtime or profile. Store outcomes and reasons indefinitely; do not keep declined weights just because their test history is valuable.

A new test round is unfinished until relevant rankings, generated policy, installed winners, live auto selection and documentation agree. Do not combine non-English results with English or confuse moderation with general-image scoring.
