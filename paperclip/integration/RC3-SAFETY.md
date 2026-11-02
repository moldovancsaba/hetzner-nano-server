# Source exchange RC3 recovery and processing boundaries

Wire version remains 1.1. Deploy the matching canonical artifact and adapter pin together. RC3 requires RC3 consumer behavior before source admission. No source, event, gap-task or destination-write switch is enabled by releasing these files.

## Durable state

The broker opens existing state only. For first commissioning, use `python -m exchange.manage initialize --database <new-private-path> --reason <bounded-commissioning-reason>` from the installed integration directory. Initialization refuses an existing file. Missing tables, unsupported versions and missing generation fail closed. Never initialize after losing acknowledged work: recover private receipts and reconcile destination effects instead.

Factory exchange schema installation is explicit: while the factory service is stopped and drained according to the operating runbook, take and verify a consistent private backup, open the existing native database, call `exchange.factory.initialize(db, create=True)` and commit. All eight tables install atomically; partial existing exchange state refuses initialization. Normal hooks call `initialize(db)` to validate state only. Do not restart or replace native worker files as part of metadata deployment.

A replacement consumer must have a newly enrolled inbox identity. Unfinished source work redelivers to the new inbox even if the old inbox saved its transport receipt. Completed source work does not redeliver. Events can redeliver to rebuild a new causal projection. Old leases are fenced. A restored broker needs offline generation rotation and receipt/effect reconciliation before claims resume.

## Claims and expiry

A bounded transport turn starts a claim only when it has room for the claim and durable receipt. One-item claims use a five-minute lease; saving the inbox/projection and acknowledgment happen in the same existing turn. Lost replies preserve original request bytes and identities. Expired sources can be claimed only for explicit expiry disposition; they cannot enter source fetching, model work or catalog writes. The expiry receipt and one stable bounded gap intent commit together.

Fresh observations use a versioned identity over all immutable envelope fields. Retrying an old request preserves its exact saved bytes. The repair root is inherited across observations, and evidence fingerprints exclude packet IDs and observation timestamps, so refreshed timestamps cannot reset the two-repairs-per-72-hours limit. New native gap tasks use exact durable idempotency and verify company, project, title, description and bounded returned identity before recording delivery.

## OpenClaw prewrite boundary

Imported candidates are paused when business imports or destination delegation is disabled, including candidates already queued. Before fetching, saved packet hashes, source links, scope and expiry must match. The freshest active observation supplies the page; proven name/address/scope coalesces one branch across official URLs. Before any model or write, transferred address quotes, official ownership, youth service and application-owned location resolution are checked against the actual fetched page. Resolver and fetch outages remain unexamined work. Changed evidence closes that observation and requests bounded repair. Source failure does not create a provider-wide terminal verdict. Imported writes require the delegated path and cannot fall back to legacy ingest.

## Evidence limits

The isolated transport, native factory, OpenClaw and GDS browser suites cover these faults without production source traffic or destination fixtures. They do not establish restore RPO/RTO, an adopted retention policy, manual screen-reader acceptance, comparative yield or the required natural shadow/live pilot. Admission, claims, imports, writer grants and all existing schedules remain unchanged until their separate cutover gates pass.
