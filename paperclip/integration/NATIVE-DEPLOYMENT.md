# Native factory hook deployment

The metadata broker and GDS views have a separate release path from the native factory. `ops/deploy_factory.py` inserts only the owned evidence-transaction and existing-coordinator hooks into the current server sources. It never uploads local worker.py or autonomy.py wholesale. Existing search, program, publishing and other developers' changes are preserved.

Run without `--apply` first. Supply the freshly observed SHA-256 of both native source files using `--expected-worker-sha256` and `--expected-autonomy-sha256`. The helper refuses source drift, ambiguous insertion boundaries, missing native state, invalid source, or enabled source-exchange business flags. The installed canonical exchange module must already import successfully. The preflight performs no research, task execution or destination write.

With `--apply`, busy work is a hold: both active ledger runs and HTTP handler threads must be absent. The helper pauses the exact idle process through a Linux pidfd, verifies its stopped state and repeats both checks, then queues termination before resuming. This prevents a new handler starting between the final idle check and termination. It never kills a running handler to make the release proceed. Unsupported process control or failed checks refuse the release; resume is attempted on every exit path.

The stopped service receives a private consistent SQLite backup with integrity verification. The helper explicitly installs the eight empty exchange tables, preserving all existing native tables, then atomically installs the three source files and a systemd module-path drop-in. The factory configuration, native schedules, budgets, credentials and publishing switches are unchanged. Source business flags remain absent/off. Starting the service is followed by its read-only health check.

If a release fails before the service starts, prior source and unit configuration are restored and the service is started. If the new service has begun native work, rollback first requires the same idle checks; a running task is preserved and the release reports a recovery hold. The forensic SQLite backup is never copied over a newer business database. The empty additive exchange schema can remain during code rollback. Preserve its receipts once exchange work is enabled.

Before enabling source hooks, complete source policy/scope enrollment, secure native machine credential provisioning, matching broker/Mac flags and natural shadow observation. This disabled-hook deployment does not authorize a writer grant, source admission, queue migration, business import or additional schedule. Recovery tests use temporary isolated stores and actual child-process death; they establish local transaction/receipt behavior, not production RPO/RTO or pilot yield.

## Multi-client feedback and turn budget

The existing coordinator's exchange slice shares a thirty-second deadline. Broker requests use the remaining allowance. Native gap-task creation begins only when its existing call timeout fits that allowance; a timeout cannot grant more work to the slice. The coordinator continues its ordinary native duties after an unavailable or malformed exchange configuration.

event_scopes may explicitly enroll up to eight unique application/client pairs. Each additional scope requires a distinct producer identity, credential and durable event inbox. The selection cursor rotates scopes across existing turns. Claims reserve enough request slots for the bounded returned batch and every acknowledgment; the response scope must match its exact saved claim body. Held work for one enrolled scope does not prevent choosing another. Batch handling improves feedback capacity without a new timer or a production-throughput claim. Keep observing actual queue age and saturation before expansion.

## Scoped module repair during source-only operation

Use deploy_factory.py --exchange-module-only --expected-module-sha256 <current-digest> to prepare a replacement of source_exchange.py only. Preflight checks the exact current digest and native idleness; --apply uses the same final paused idle check, consistent private backup, health gate and code-only rollback. Caller hooks, active source flags, credentials, native schedules and all other configuration remain byte-for-byte unchanged. No schema initialization is performed in this mode. A busy service refuses the attempt instead of cancelling work.

Native machine tokens may come from systemd CREDENTIALS_DIRECTORY. Managed read-only credentials use a protected directory and file owned by root or the service identity; only modes 0400, 0440 and 0600 are accepted. Outside that directory, the existing private-file rule remains. Symlinks, non-regular files, shared writes, public reads, overlong values and control characters are refused before network access. Never log token values.

## Reviewed per-project catalog handoff

The three native ClassScout writer entry points (publication, contact/description refresh and structured program updates) check source_exchange.destination_handoffs before any dependency work. No handoff entry means their existing behavior continues. An entry for a different project does not change this project. A selected project with a valid handoff is held before any fetch, model, packet reservation or catalog request; existing receipts and packets remain available for separate reconciliation. Malformed selected handoff data fails closed. Source research/verified-page export uses its existing controls and is unaffected.

A reviewed destination_handoffs entry maps the exact native project ID to scope, writer openclaw, a positive integer writer_epoch and immutable review_ref. Scope must equal that project's existing source enrollment. Installing code does not add this configuration. Source-only protocol approval cannot enable a destination handoff or grant.

Use deploy_factory.py --writer-handoff-hooks with exact current module, publishing, refresh and program digests for a source-preserving release. The helper inserts only the reviewed guard into the current host functions, compiles all four modules, uses the existing paused idle gate and private consistent backup, and preserves configuration/schedules. A source mismatch or running handler aborts. Failure restores every prior module without replacing the business database. The unrelated worker, autonomy and search-workflow sources are not replaced.

## Client-isolated producer credentials

The original native producer identity and credential remain scoped to ClassScout NYC. `source_exchange.scope_credentials` maps an exact `application/client` key to a matching `scope`, private absolute `token_file`, and distinct UUID `event_inbox_id`. Additional clients never fall back to the NYC credential. Credential paths and inbox identifiers cannot be shared between configured scopes. Enrollment must also install a matching single-scope broker principal; the runtime cannot grant itself another scope.

Offer delivery selects credentials from the saved offer scope while preserving its request bytes and operation ID. Event status, claims and receipts select the exact saved scope and inbox. A missing credential or changed inbox holds pending work instead of switching identities or generating replacement receipts. Existing NYC operations keep their original inbox and key. Dashboard/reporting access is commissioned separately.

Deploy the selector through the module-only helper before preparing an enrollment manifest. Each enrollment binds its producer project, independent source-policy review, reader inbox, producer inbox and private credential preparation. Preserve credentials with the private ledgers during recovery. New credentials and source flags require that exact enrollment review; installing the selector alone changes no scopes, tokens, flags, budgets or schedules.

## Management and SLG writer entry points

`destination_handoff.py` validates an exact reviewed project/application/client handoff before Management's shared engine write reservation, the Padel evidence-intake workflow, or SLG's CRM mutation reservation. A selected handoff must match the source-enrolled project, external writer, positive epoch and immutable review reference. A malformed selected authority holds the mutation. Unselected projects and all read-only catalog/CRM work retain their existing behavior. The guard preserves existing packets for separate outcome reconciliation.

Use `--writer-handoff-hooks --application-writers` with the exact current source module, ClassScout writer and application writer digests. Supply `--expected-destination-guard-sha256` if that module already exists; unexpected prior code refuses the release. The helper patches only the exact mutation entry points in the current host code, preserving unrelated changes. It uses the existing private backup, paused idle check, health verification and code-only rollback. Configuration, permissions, source scope, project registration and schedules are not changed. A source-shadow review cannot authorize a destination handoff.

Process control never freezes the service-manager unit. The final paused check must still find the same PID, no active ledger run and a single thread. A Linux pidfd prevents PID reuse from redirecting signals. An automatic restart policy that can revive a cleanly terminated process requires a separate drain protocol. Stop-control failure restarts the original service if it has exited; no configuration has changed at that point.
