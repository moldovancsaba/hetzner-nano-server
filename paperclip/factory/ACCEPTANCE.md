# Source-page acceptance — 2026-10-27 UTC

ClassScout is the owner-selected pilot; broad search is disabled. Evidence: [acceptance.json](acceptance.json).

| Task | Result |
| --- | --- |
| NAR-6, Dodge YMCA research | Draft with source-supported name, address, phone and activities; assigned to local-board in review |
| NAR-7, independent evidence recheck | All four stored fields rechecked against the fetched source; no changed facts or missing name/address; human review still required |
| NAR-8, provider contact support reply | Source-backed reply prepared; assigned to local-board in review; no customer delivery |
| NAR-10, missing-source negative case | No inference; pending human clarification and blocked owner assignment; synthetic task subsequently cancelled so no user answer is required |

The successful research pass took 86.2 seconds inside the worker; support took 106.0 seconds; deterministic quality recheck took 1.3 seconds after admission. These times include source/model waiting, exclude waiting for the single worker slot, and are individual examples rather than throughput or latency guarantees. Research used the 8,192-token profile, with 993 input and 287 output tokens. The source page was small; this does not certify arbitrary 8K research workloads.

15 local and server unit checks passed, covering public-network restrictions, redirects, bounded decompression, robots refusal, script exclusion, evidence matching, unknown fields, source limits, repeated draft upserts, support/listing state separation, safe evidence rendering and assigned task selection. All 16 live password/session/API/WebSocket gate checks passed.

Initial setup exposed two Paperclip contract errors: review needed a named human reviewer, and agents cannot name a human as an unblock-descriptor owner. Both were corrected using supported API workflows. The original failed research run was reconciled through the official typed recovery endpoint with verified partial effects before its successful retry. NAR-9 is a cancelled, superseded negative test. Failed attempts remain in the audit evidence.

Paperclip stops the process adapter when the task is reassigned from the agent to the owner. The heartbeat run therefore records an expected `cancelled` / `issue_reassigned` with `reassignmentStopConfirmed`, while the worker records completed work and the persisted task is in review. These expected handoff stops were verified; they are distinct from the initial execution failures.

Limitations: one provider and a narrow contact question; no general web search, adversarial end-to-end evaluation, conflicting-source resolution, closure detection, live application publishing, customer delivery or full recovery restore drill (as of that date; an isolated application restore drill has since passed, see [WORKFLOWS.md](WORKFLOWS.md)). Literal source evidence still requires human factual and editorial review. No recurring agent heartbeats were enabled. Backlog tasks record the later integrations and operating decisions.

Recovery: a restricted server archive and ignored off-server `private/paperclip/factory-recovery.tar.gz` copy were saved. The archive includes worker code, configuration, service unit and a consistent SQLite snapshot; the extracted snapshot passed `PRAGMA integrity_check`. This is a one-time recovery copy, not recurring off-site protection. All three agents were idle at final handoff with recurring heartbeats disabled; worker health was OK.
