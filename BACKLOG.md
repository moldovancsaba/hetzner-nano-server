# Hetzner model research and data-management backlog

Owner: platform operator. Updated 2026-10-30. This is the repository's task backlog; [the operating plan](docs/CONTINUOUS-EVALUATION.md) defines execution and [retention policy](docs/DATA-RETENTION.md) defines data boundaries.

## Delivered

| ID | Priority | Item | Acceptance evidence |
| --- | --- | --- | --- |
| MR-01 | P0 | Daily server-side metadata discovery | Enabled systemd timer, 03:30–03:45 Europe/Budapest; first run fetched all 12 feeds successfully |
| MR-02 | P0 | Preserve tested/declined model information | 52 attempted variants indexed after Round 6 (38 after round 4, the evidence this item was first accepted on); failure sources, decisions and removed artifact digests versioned |
| MR-03 | P0 | Separate discovery from inference | Collector performs metadata-only reads; no weight installation, inference, customer-request access or default changes |
| MD-01 | P0 | Ranking-based defaults and installed alternatives | Existing model policy, API discovery, exact-digest gates and shared queue |
| DR-01 | P0 | Remove declined weights, retain evidence | Qwen3-VL 2B and Ministral 3B removed; metadata audit retained; about 11 GiB free afterward |
| DR-02 | P0 | Minimize transient job data | Five-minute memory result TTL, active periodic expiry and authenticated DELETE acknowledgement for result/queued-job removal |
| TR-01 | P0 | Define training boundary | Owner approved curated, explicitly approved datasets and labels only; never capture live Camera inputs or conversations |

| ST-01 | P1 | Content-free production model-demand tracking | Persistent model/digest/count/last-valid-request metadata; tests explicitly excluded |
| ST-02 | P1 | Automatic top-three / 3-day weight cleanup | Hourly timer, idle gateway lease, deletion audit and real disposable-alias verification. Window set to 3 days and the initial history grace ended by owner decision 2026-10-30; the first run under the new rule removed ten lower-ranked models and took the AI host disk from 85% to 51% |

| EV-05 | P1 | Ten additional text/image candidates (owner-requested round 4) | Five English text and five general image candidates attempted under an exclusive maintenance lease; results and independent rankings in [round 4](benchmarks/round4/REPORT.md) |
| EV-09 | P1 | Four further candidates, full suites (owner-requested round 6) | LFM2 1.2B and OLMo 2 1B (English plus separate Hungarian), SmolVLM2 256M and InternVL3.5 1B (recognition and moderation); no ranking change, 52 variants indexed; InternVL incomplete because of a runner fault; see [round 6](benchmarks/round6/REPORT.md). Policy id 2fa66c02 and the 52-variant dashboard deployed and verified 2026-10-29 (11/11 public checks, [record](benchmarks/round6/deployment.json)) |
| EV-06 | P1 | Three further variants and Q5 recognition (owner-requested round 5) | gemma3:270m, LFM2.5-350M and MiniCPM-V 4.6 Q5_K_M evaluated; Q5 leads recognition on the frozen 32-image cohort; see [round 5](benchmarks/round5/REPORT.md) |
| OP-01 | P1 | Meaningful failure notification | Debounced alerts (three consecutive checks), delivered in chat since 2026-10-28, for the gateway, chat, Caddy and Docker services, the inference container and its OOM kills, an open inference circuit, a stuck job or long queue wait, metrics failures, disk space, repeated failures, high latency and authorization or availability errors per project, plus an independent host-reachability check. The model-discovery and cleanup timers and discovery source failures are not monitored. Email is deliberately disabled by the owner; see [observability](docs/OBSERVABILITY.md) |
| CX-01 | P1 | Verified 8K default text context | Default ClassScout, Habigoal and Pandora text match Paperclip at 8192 tokens with token budgeting; synthetic 4K/8K/16K/32K evidence in [paperclip-context](benchmarks/paperclip-context/README.md); committed 2026-10-29, see [CHATBOT-CONTEXT](docs/CHATBOT-CONTEXT.md) |
| HU-01 | P2 | Separate experimental Hungarian route | `text_chat_hu` with its own ranking; three follow-up rounds so far, none passes the 20/24 gate; experimental and not for unattended coaching; see [Hungarian](docs/HUNGARIAN.md) |

## Broader Camera evaluation — delivered

Recognition is complete on 32 public research photographs, with nine paired robustness variants and eight separate counting probes. MiniCPM-V 4.6 1B was the recognition default from this comparison; since Round 5 the MiniCPM-V 4.6 Q5_K_M variant leads the same cohort and is the deployed default; [results and limits](benchmarks/vision-evaluation/REPORT-RECOGNITION.md). The separate 41-image, nine-category moderation comparison is complete; Qwen3.5 0.8B is the deployed moderation default. [Full results](benchmarks/vision-evaluation/REPORT.md) include category misses, false alarms, trivial baselines and paired robustness. This does not close EV-01/EV-03: representative private holdouts, more positives, independent human labels, age/identity provenance and broader violence/hate-word coverage remain needed. No live Camera data is used or retained for training.

## Ready / next

| ID | Priority | Work | Definition of done |
| --- | --- | --- | --- |
| MR-04 | P1 | Review the initial shortlist and choose at most two candidates | Verify publisher, license, precise artifact/quantization/projector size, ARM64/runtime compatibility, changed condition versus prior attempts, intended task and test budget |
| EV-01 | P1 | Build approved unseen project holdouts | Versioned manifests, provenance/approval and labels; English structured tasks, general images and each moderation category scored separately; no training contamination |
| EV-02 | P1 | Standardize maintenance-window benchmark runner | Drain public queue, isolate native testing, pin resource limits, capture real peaks/OOM/load/switch times, enforce download/time/disk limits, restore and verify all services |
| EV-03 | P1 | Extend public moderation testing with representative unseen holdouts | Enough positive, negative and ambiguous examples per category, independent label review, explicit-act/photographic gesture/hate-symbol/violence coverage gaps addressed; never auto-clear images |
| EV-07 | P1 | Evaluate a separate visible-text moderation path | Both broad-cohort leaders detected 0/2 hate-word positives; compare OCR plus a reviewed text-classification/rules path on more English positives, anti-hate context and lookalikes before deployment; non-English separate |
| CL-01 | P1 | Integrate result acknowledgement in clients | Camera/ClassScout poll, consume and DELETE terminal results; preserve source revision and manual-review behavior; update client contracts in their own repositories |
| EV-10 | P2 | Fix runner stop/resume handling and complete InternVL3.5 1B | `StopIteration` after 9 of 32 cases must not end a candidate and `resume.py` must retry an incomplete stop; then one owner-approved maintenance window (about 2 hours) for the remaining recognition, robustness, counting and moderation cases. Repeating on the unfixed harness is barred |

## Planned

| ID | Priority | Work | Definition of done |
| --- | --- | --- | --- |
| EV-08 | P2 | Isolate recognition quantization versus thinking profile | Full fresh paired Q4/Q5 cohort with identical explicit non-thinking profiles and case order; repeated runs/holdouts before claiming precision alone caused the Round 5 gain |
| RT-01 | P2 | Evaluate LFM3 runtime support in isolation | Current runtime reports unknown lfm3 architecture for text and vision; test a pinned compatible runtime with regression, memory, 8K context and rollback evidence before any production upgrade |
| RT-02 | P2 | Investigate decision-model API separately | d1-omni-600M does not support the generation endpoint; design and benchmark its decision/scoring contract before treating it as image recognition or moderation |
| MR-05 | P2 | Improve artifact-family identity and revision matching | Distinguish architecture, base model, fine-tune, quantization, encoder/projector and revision; changed artifact/runtime triggers reviewed retest, not repetitive unchanged tests |
| EV-04 | P2 | Use weekly review and fortnightly approved test windows | Operator checklist followed; no unattended benchmark/generation schedule added until queue isolation and recovery are proven |
| TR-02 | P2 | Create an approved dataset/training registry | Each version has provenance, permissions, approval, split, labels, checksum, retention/revocation and access controls; raw files outside public Git and inference request storage |
| TR-03 | P2 | Plan actual training separately | Off-server compute/storage/run manifests, approved dataset version, adapter/weight provenance, holdout evaluation and rollback; never train on the production queue |
| OP-02 | P2 | Test metadata/config backup and restore | Encrypted off-host backup of approved metadata/config manifests and separately protected secrets; exclude transient requests and job results Owner decision 2026-10-29: acceptable without it for now; revisit later. |
| OP-05 | P2 | Calibrate latency alerts per tenant and job type | One 60 s p95 rule currently covers every tenant; measured p95 over 24 h was about 95 s for Paperclip, 134 s for Habigoal and 35 s for ClassScout, so it flaps. Set thresholds from measured behaviour per tenant and task. Owner decision 2026-10-29: acceptable for now; revisit later |
| DR-03 | P2 | Assess strict RAM-cache privacy mode | Measure shorter model keep-alive/unload-after-job tradeoff; document that ordinary memory freeing is not forensic secure erasure |
| OP-03 | P2 | Consider durable queue only if needed | Explicit privacy/storage design and deletion semantics before persisting any customer payload; current queue stays memory-only |

## Decision rules

A model progresses through discovered → needs_review → ready_to_test → testing → accepted / declined / deferred. Reconsider a declined model only with a recorded changed artifact, runtime or profile. Store outcomes and reasons indefinitely; do not keep declined weights just because their test history is valuable.

A new test round is unfinished until relevant rankings, generated policy, installed winners, live auto selection and documentation agree. Do not combine non-English results with English or confuse moderation with general-image scoring.

## Follow-up from Camera coverage and Hungarian audit · 2026-10-28

- Camera: acquire/freeze fresh public held-out positives and hard negatives for all twelve reasons, with event-specific brand/political/other rules; keep human approval. Existing evidence covers only six reasons partially.
- Camera: validate the Qwen + LFM2.5-VL 450M pair prospectively, measuring extra true concerns, false alarms, abstention, total job latency and switching cost; do not add a redundant third NSFW detector. Evaluate OCR/logo/gesture and quality components against the remaining gaps.
- Hungarian: no Apertus Mini promotion after failed quality tests. Evaluate Phi-4 Mini and Hungarian PULI at useful quantization/context on adequate hardware, then require the original gate plus held-out Habi role/date/correction regressions. No hardware purchase or external inference is authorized by this backlog entry.
