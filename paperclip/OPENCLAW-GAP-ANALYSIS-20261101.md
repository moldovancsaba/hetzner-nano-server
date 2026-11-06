# OpenClaw and Paperclip: operational audit and transfer plan

Audit date: 1 November 2026, Europe/Budapest. Current measurements were captured around 19:23 Budapest. This document is a dated assessment; [the generated evidence snapshot](OPENCLAW-COMPARISON-20261101.json) owns the measurements and source hashes.

## Assessment

OpenClaw has the broader production operation: eight client scopes, uniform discovery/enrichment/maintenance/polish/audit jobs, several source feeders, live SLG discovery and a working owner-report channel. Paperclip has a more explicit company task trail, independent research-to-quality handoffs, durable publication/update packets, uncertain-write protection and stronger public-web transport controls.

Both systems are primarily deterministic Python workflows around bounded model calls. The agent names do not imply autonomous employees choosing arbitrary actions. Their surrounding application pipelines, scopes, evidence gates and scheduled controllers determine what they can actually do.

The strongest next step is coordinated specialization. Keep proven OpenClaw workers running, improve Paperclip with reusable source and selection mechanisms, and standardize evidence and write outcomes between them. Migrating everything or merely adding more agents would not address the largest shared risks.

## What was inspected

- OpenClaw installation instructions, workspace authority, current handover, jobs, model/source policies and reliability design.
- Actual job switchboard, recent worker history, discovery telemetry, cron status, resident Ollama context, alerts and backup dates. No secret configuration or private provenance ledger was opened.
- Worker scheduling, discovery, official-page recovery, shared time budgets, source reads, content checks, provenance persistence, circuit-breaker wiring and SLG submission code.
- Paperclip factory source, deployed health/configuration subset and read-only database aggregates; the earlier delivery acceptance and hashes.

OpenClaw was left unchanged. No business job, inference call, paid search, external message, deployment or schedule change was triggered for this audit. Existing generated snapshots from earlier today were treated as historical evidence and refreshed where relevant.

This is an audit of these installations, not a claim about every capability of upstream OpenClaw or upstream Paperclip. No controlled same-input quality/speed comparison was performed.

## How OpenClaw operates here

The outer `/Users/Shared/Projects/OpenClaw` repository is the host installation. The real research operation is a separate repository at `.openclaw/workspace`. The installed runtime reports OpenClaw 2026.7.1-2; the workspace source revision is recorded in the snapshot.

OpenClaw cron and launchd trigger a serial Python worker. A content-validated internet quorum precedes dequeueing. Recognized shared dependency failures preserve the work and defer it; they are not recorded as candidate-quality failures. The worker selects enabled and due jobs, observes pacing, runs bounded batches and records results. Two Management daemons process application ingest cards under the same host lock. The ClassScout production Ollama bridge is a documented exception to that lock and belongs to ClassScout.

The job registry currently enables 40 jobs: five operations for each of NYC, BOS, LA, Padel Africa, Sportolok, cogmap, seyu and dvsc. The eight visible enabled cron entries cover worker ticks, model keepalive, checks, owner reports and four discovery seeders. Jobs and cron are separate registries; counting only one misses the operation.

Research uses deterministic search/fetch helpers. Qwen2.5:7b is actually resident at 32,768 context tokens. English polish uses Apple's local model according to the active job implementation; Sportolok's Hungarian polish uses Ollama. Public-only Muse source/contact assistance is narrowly bounded; its existence does not prove successful assistance in every run. Jev is a shadow integration gated on a key and pinned model, not an enabled production decision-maker.

The flow is search/seed → source/identity/territory checks → extraction/content gates → application API submission → separate readback where available. Management acceptance creates an ingest card; its downstream application pipeline decides publication.

## Capability comparison

| Area | OpenClaw here | Paperclip factory here | Gap or transfer |
| --- | --- | --- | --- |
| Business scope | Eight configured clients across three applications | ClassScout, two Management clients; SLG project present but unconfigured | Reuse client registry and due-aware operation coverage; a project is not a connected service |
| Company visibility | Job histories and hourly WhatsApp owner report; local admin intentionally stopped | Five named roles, task links, company dashboard, 19 registered routines | Give OpenClaw linked task/outcome visibility without duplicating its scheduler |
| New-source discovery | OSM, directories, SearXNG/engine rotation, licensed-plan-gated Mojeek cache and search cursors | Budgeted Brave plus direct source research and targeted gap searches | Add diverse source feeders to Paperclip before increasing its search rate |
| Selection | Gap-first enrichment, oldest-attempt maintenance, scarcity/query rotation, evidence-sensitive terminal refusals | Catalog/growth cursors, freshness and bounded follow-ups/program rotation | Port selection principles and source-yield accounting, adapted to Paperclip's schema |
| Source evidence | Ownership/robots/page-value checks; SLG field/contact provenance retained privately | Literal quote/value validation, page hashes, timestamps and independent QA | Standardize a portable evidence packet, preserving independent review |
| Web transport | General page/robots paths use urllib; focused linked-page helper refuses redirects | Public DNS validation and pinned connection, redirect revalidation, body limits | Transfer the hardened transport to OpenClaw's actual fetch paths |
| Publishing and updates | Automatic application-gated writes; accepted submissions and readback reported separately | Durable request/proof/receipt packets, source/baseline checks, uncertain holds and bounded renewal | Transfer packet and reconciliation design to OpenClaw rather than copying business payloads |
| Structured programs | General enrichment and price/schedule machinery; catalog orchestration exists but is disabled | Enabled program checks preserve unmatched programs and require supported changes | Compare schemas first; reuse Paperclip's conservative program update contract |
| SLG | Real recurring lead discovery, enrichment, maintenance, polish and audits | Six-tool MCP client exists; no configured brand/key; CRM write helper has no calling workflow | Reuse discovery logic with a separately scoped credential and explicit ownership |
| Customer communication | Owner WhatsApp report works; lead creation does not establish prospect messaging | Support drafts; no outbound sender workflow | Neither evidence set proves an automated sales conversation loop |
| Failure recovery | Shared dependency deferral, fail-closed ledgers, due-aware queueing; breaker code exists | Native monitors, bounded successors, exact receipts, stale packet renewal | Shared outcome vocabulary and observable recovery, without clearing history |
| Backup/recovery | Scheduled backups intentionally disabled; dated local backup exists | Server snapshots and off-server backup; prior restore proof | A policy change is needed before restoring OpenClaw schedules; full failover remains unproven |
| Model/context | Resident 7B model, 32K context, GPU; host shows heavy swap | Shared CPU inference, Granite auto route, 8K; budgeted public-only remote assistance | Context size is capacity, not a measured quality win; retain assignments pending matched evaluation |

## What the measurements support

The fresh 24-hour OpenClaw history contains 45 discovery runs and ten reported deliveries: cogmap 0, seyu 1, dvsc 1, BOS 1, LA 0, NYC 1, Padel Africa 2 and Sportolok 4. LA includes one failed run with unknown yield. These are worker-reported acceptance counts, not ten independently verified public listings. They do show that live lead and catalog discovery exist; they also show low yield despite many jobs completing successfully.

Observed blockers include missing sourced addresses, source/organization mismatch, unreadable pages, missing reachable contacts, SLG quality-gate rejection and exhausted stage budgets. Increasing concurrency or relaxing evidence checks would not reliably solve these. The latest SLG run even accepted a source whose name alone does not establish target suitability; evaluate a sampled accepted cohort against the client's actual settings before calling discovery commercially effective.

Paperclip currently records 15 published ClassScout packets and 38 applied refresh packets cumulatively. These are durable ledger statuses, not a fresh full-catalog readback. Its Management ledger separately records two accepted packets and one published packet. The earlier release acceptance includes verified destination checks. These different windows and meanings cannot be used to claim Paperclip outperforms OpenClaw.

Paperclip is healthy, search/publishing/program updates and both engine clients are enabled. SLG still has an empty brand list, CRM writes disabled and delivery disabled. There is no dedicated Sales Agent in its five-role registry. All eight historical search attention rows remain; old failures must be assessed with their successor receipts rather than counted as eight new unresolved incidents.

OpenClaw's latest hourly report delivery is recorded as delivered, and its support cron reports no consecutive errors. The alert snapshot warns about disk and swap. A fresh host read found roughly 17.7 GiB free and 12.6 GiB swap in use; the earlier alert has a different timestamp. Swap use is a capacity warning, not proof of current swapping or an inference slowdown. Do not infer a throughput number from it.

## Prioritized gaps and deliverables

Effort below is an engineering estimate, not a commitment or a paid-call quota. Acceptance criteria are part of each proposed delivery.

| Priority | Deliverable and owner | Recommendation | Estimated effort / calls | Risk and acceptance |
| --- | --- | --- | --- | --- |
| P0 | Destination-side writer coordination; ClassScout/Management API owners plus both integrations | Deliver first | 2–4 days; controlled fixture and exact-record readbacks | Independent locks cannot protect the same destination. Require stable operation IDs, record revisions/conditional writes, field ownership and an explicit conflict response. Two simultaneous writers must never silently overwrite each other. Local read-before-write alone is insufficient. |
| P0 | One shared search-account budget broker, or clearly separated accounts | Deliver before scaling | 1–2 days; offline quota tests and at most one authorized probe | Paperclip's 1,800 allowance and OpenClaw's 1,200 ceiling cannot jointly guarantee a shared 2,000 account cap. OpenClaw currently blocks durable Brave discovery, so this is a scaling/configuration risk rather than proof of current overspending. Reserve attempts atomically and retain uncertain usage. |
| P0 | Bounded public-web transport in OpenClaw's source, robots and image paths | Deliver | 1–2 days; adversarial local fixtures, no attack on production | General urllib paths do not show Paperclip's public-IP/pinned-DNS protection; some redirects and reads are broader. Test private/loopback targets, DNS changes, redirected hosts, compression/body limits and credential-bearing URLs. Preserve existing source/ownership policy. |
| P1 | Management exact-card delivery readback | Deliver in Management, consumed by both | 1–2 days; controlled API cases | Accepted cards must not count as publication. Implement bounded instance-scoped exact card/listing reads and explicit missing/unavailable states. Existing request: OpenClaw `MANAGEMENT-DELIVERY-READBACK-REQUEST.md`. |
| P1 | OSM/directory feeders and source-yield rotation in Paperclip | Deliver incrementally | 2–3 days; fixtures then natural scheduled runs | Prevent a second independent candidate backlog. Deduplicate branch identities, retain source permissions, and measure qualified/accepted/readback stages by source. Use discovery effort on low-coverage eligible areas. |
| P1 | Common evidence and result contract | Deliver | 2–3 days; offline contract fixtures and a bounded read-only pilot | Carry application/client, branch identity, exact URL, fetch time/hash, field/value/quote, checker version and task/operation IDs. Outcomes distinguish not checked, rejected, accepted, readback-confirmed and public. Never treat another worker's prose as source evidence. |
| P1 | OpenClaw durable write packets and uncertain-outcome reconciliation | Deliver by application | 2–4 days; loss-of-response/concurrent-write fixtures | Atomic JSON replacement prevents truncated files but is not a cross-process transaction or a destination write receipt. Record intent before sending, bind returned identity to the request, confirm supported fields and hold unknown outcomes. Retrying a timeout must not duplicate or erase data. |
| P1 | SLG scoped integration and workflow ownership | Deliver after explicit workspace/key provision | 1–2 days after required inputs; authenticated read checks | Keep OpenClaw's existing client ownership. Do not silently copy its legacy shared credential or infer a workspace. Paperclip can first expose connection/pipeline/briefing tasks. Automatic capture needs a real calling workflow, independently evidenced contact fit and field readback. |
| P2 | Outcome dashboard across systems | Deliver after common contract | 1–2 days; no paid calls needed | Show verified new records, confirmed updates, evidence holds, queue age, source yield, search consumption and freshness. No invented revenue or model-cost savings. Link to the owning task rather than duplicate counts without timestamps. |
| P2 | Repair/backup policy review and recovery drill | Deliver proposal; do not enable disabled jobs during audit | Half-day inventory; 1–2 days for an approved rehearsal | OpenClaw self-repair and backup schedules are intentionally off. Breaker code is not evidence of an active breaker loop. Demonstrate isolated restore of ledgers/configuration and distinguish it from whole-host recovery. |
| P2 | Matched model/workflow evaluation | Deliver before any routing/context change | 1–2 days; small fixed benchmark, marked as test | Use identical public pages, schemas and gates. Measure factual precision, missing-field recovery, false acceptance, total latency and memory. Freeze OpenClaw's existing assignment and Paperclip's 8K until a separately authorized change. |

## Bidirectional transfer boundaries

Bring OpenClaw's source diversification, application-driven client scope, gap/maintenance distinction, due-aware scheduling, query rotation and per-source stage measurements into Paperclip. Reuse the mechanisms and contracts; copying scripts that hard-code their workspace, credentials or API vocabulary would create a second source of truth.

Give OpenClaw Paperclip's hardened public-web transport, request/proof/receipt lifecycle, ambiguous-write holds, bounded renewal and exact task receipt checks. Expose its jobs in Paperclip through a small adapter that creates one durable task per operation and links the resulting evidence/outcome. The adapter should observe existing schedules first. It must not introduce a second trigger or make native agent status the business-outcome authority.

Use common destination APIs for conflict control and publication status. Sharing a local SQLite database or file lock between the Mac and Hetzner is not an appropriate substitute.

## What should remain separate

- Owner operational reports, support drafts and prospect campaigns have different recipients and authorization. A working WhatsApp report does not authorize customer messaging.
- OpenClaw's 32K window and Paperclip's 8K window have different hardware and workloads. No automatic context/model migration follows from this audit.
- Internal source-storage policy differs between the systems. Paperclip retains independently fetched evidence while discarding raw Brave results; OpenClaw blocks durable Brave discovery and gates Mojeek storage on its configured plan. Do not merge the policies without confirming the applicable account rights. This audit does not adjudicate external license terms.
- An OpenClaw maintenance attempt timestamp must not be imported as a successful field verification. Preserve attempted-at, verified-at and changed-at separately, especially for unavailable sources.
- OpenClaw's disabled catalog/learning/repair/admin/backup activities remain disabled. Their code is available, not evidence that they are operating.
- No automatic sales campaign, shared credential migration, forced job run, gate relaxation or application patch was performed here.

## Delivery order

Start with destination conflict controls and shared quota ownership. Then harden OpenClaw fetching and implement exact Management delivery readback. Add the common evidence contract and an observation-only OpenClaw-to-Paperclip adapter. Finally expand Paperclip discovery and activate the explicitly chosen SLG workspace, measuring natural-run results before increasing work rates.

The target is one observable company with clear worker ownership and independently verifiable outputs. Neither replacing the Mac operation wholesale nor leaving two uncoordinated writers addresses that target.

## Source map

OpenClaw workspace files reviewed: `SSOT.md`, `HANDOVER.md`, `JOBS.md`, `AGENTS.md`, `RELIABILITY.md`, `MODEL-POLICY.md`, `LEDGER.md`, `jobs.json`, `worker.py`, `discover.py`, `cs_create.py`, `enrich.py`, `websearch.py`, `official_evidence.py`, `work_budget.py`, `discovery_search.py`, `discovery_performance.py`, `discovery_telemetry.py`, `local_state.py`, `provledger.py`, `slg_maintain.py`, `cs_maintain.py`, `mgmt_maintain.py`, `contentcheck.py`, `job_breaker.py` and `MANAGEMENT-DELIVERY-READBACK-REQUEST.md`.

Paperclip files reviewed: `factory/worker.py`, `net.py`, `evidence.py`, `publishing.py`, `refresh.py`, `portfolio.py`, `engine_ops.py`, `company_ops.py`, `slg.py`, `BRAVE.md`, `SLG.md`, `WORKFLOWS.md`, plus the stage 1–4 deployment and acceptance artifacts. Source hashes in the snapshot identify the reviewed versions. Existing unrelated worktree changes were preserved.
