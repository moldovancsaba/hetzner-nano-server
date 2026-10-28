# Operational reporting and alerts

Implemented 28 October 2026. Request content remains transient; this system records service behavior only. It does not train models, retain client images/conversations, change rankings, resize servers or restart stuck inference automatically.

## Usage reports

Each service key can read its own report:

```http
GET https://chatbotapi.haho.ai/v1/usage?hours=12
Authorization: Bearer <that project's key>
```

The API permits windows up to 168 hours and filters by the authenticated project. There is no public cross-project report. An authorized host operator can read all projects without modifying the database:

```sh
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 '/opt/narimato-gateway-venv/bin/python /opt/narimato-gateway/scripts/usage_report.py --hours 12'
```

Add `--project camera` or `--project classscout` to filter an operator report. The separate 14-day model-demand ledger is unchanged. Usage reporting begins at the recorded `tracking_started_at`; it cannot reconstruct missing earlier history. `full_window_tracked: false` explicitly discloses incomplete coverage, including event-cap truncation. Outcome counts use the event's timestamp, so a job admitted before a window can complete inside it.

Only requests handled by the gateway appear in HTTP counts. Proxy, TLS, network and client-side failures can occur before a request reaches it; watchdogs detect sustained reachability faults, not every failed connection. Coverage indicates retained collection history, not an uptime or delivery guarantee.

Reports separate each project and declared test/production purpose. They include admitted jobs, completion/failure, HTTP statuses and safe error codes, task/model counts, queue wait, unloading/switching, native model load time where available, inference time, end-to-end job duration, client disconnect evidence, terminal-result acknowledgments and results that expired without acknowledgment. A cold load without a previous resident model is a load, not an unload/switch. Legacy upstreams without native timing report a missing sample, not a fictitious zero.

A completed job proves server generation. A client DELETE proves only that a client acknowledged/discarded the retained result, not that a person saw it or that business validation passed. Detected socket disconnects are a lower bound; absence is not delivery proof. Each app still needs an end-to-end test of its own result handling. Unknown credentials cannot be attributed to a particular project and remain `unknown`.

## Privacy and bounded storage

The gateway's private SQLite database is `/var/lib/narimato-gateway/metrics.sqlite3`, under its existing private systemd state directory. Its fixed columns contain timestamps, normalized endpoint templates, HTTP method/status, known project/task/model identifiers, outcome/error codes, timings and disconnect flags. No request/response body, prompt, photo, image hash, job ID, idempotency key, user identity, IP, raw URL/query or credential is stored. The request log cannot create arbitrary new content fields. Unknown routes are reduced to a constant; job paths become `:id` templates.

Metadata expires after 30 days and is capped at 200,000 events, with a 64 MiB database-page ceiling and bounded WAL/checkpoint configuration. Maintenance runs on writes. Startup storage failure disables analytics and raises a visible operational fault while inference remains available; the independent model-use ledger retains its existing admission protection. Write failures do not intentionally fail otherwise valid inference. The public API reports its live write-failure counter; a standalone read-only report cannot know that in-process counter and reports null.

Always mark synthetic checks with `X-Request-Purpose: test`. The server cannot detect an unmarked test automatically. Polling/discovery/DELETE have HTTP metadata but never extend production model-demand retention. The benchmark's private reference images and approved datasets remain separate from this operational database.

## Watchdogs and notification delivery

The inference host runs `narimato-monitor.service` every 30 seconds, with a 128 MiB/10% CPU ceiling. Three consecutive samples raise or recover an alert. Identical ongoing conditions do not repeatedly notify. It checks:

- required services and the inference container;
- an open upstream circuit or an active job older than five minutes;
- oldest queue wait over 60 seconds;
- operational-metrics read/write failure;
- disk below 6 GiB (warning) or 4 GiB (critical), and OOM termination;
- at least three non-cancellation production job failures among at least five terminal jobs in 15 minutes, at a failure rate of 20% or more;
- production p95 completion above 60 seconds, with at least five completed samples;
- repeated availability/authentication errors that can be attributed safely.

Test-job failures and planned model-storage maintenance rejections do not count as client incidents. The monitor observes and reports; it never resets a failed inference circuit while upstream work might still exist.

The existing second host runs `narimato-external-watchdog.service`, independently checking the inference HTTPS gateway. It expects the unauthenticated API's 401 response and needs no inference key. These checks are explicitly marked as tests. This can detect an inference-host outage even when the local watchdog cannot run. It uses 64 MiB/5% CPU and does not modify Paperclip or its application containers.

Private status is under `/var/lib/narimato-monitor/status.json` on the inference host and `/var/lib/narimato-external-watchdog/status.json` on the second host. Status includes bounded alert/recovery history, debounce state, last email-accepted revision, retry status and whether mail credentials are configured. It contains no request content.

The owner explicitly deferred email on 28 October 2026. Email delivery is disabled on both hosts; no email was sent and no mail-sending credential was installed. Failure/recovery alerts use the in-chat scheduled check for now. That local delivery channel requires the owner's computer and app to be running, while the server watchdogs continue independently and preserve bounded status/history. If email is authorized later, use root-only environment files with a sending-only credential, a verified sender, an explicit recipient and `MONITOR_EMAIL_ENABLED=true`; never recover or expose a protected Vercel sensitive value.

Notification retries use a stable payload and idempotency key, exponential backoff and persisted delivery progress. A provider acceptance is not proof of inbox delivery. See the provider's [send API](https://resend.com/docs/api-reference/emails/send-email) and [idempotency contract](https://resend.com/blog/engineering-idempotency-keys).

An additional in-chat scheduled check is a fallback for missing/stale watchdog state or notification-delivery problems, not a substitute for the independent server check. Local scheduled runs require the owner's computer and app to remain running; see [scheduled-task execution](https://learn.chatgpt.com/docs/automations?surface=app). Email remains disabled until a new owner instruction.

## Client integration and release boundary

[Controlled real-client evidence](../results/operations-20261028/verification.json) records one Camera image job and one ClassScout text job, marked as tests, with terminal-result acknowledgment. Camera resumed the same image job in a second process without resubmission. These are real application-client calls to the deployed Hetzner API, not a claim that an unmerged Camera branch is already deployed or that an event/browser workflow passed.

Camera's draft PR #735 needed a discovery fix: installed models are returned in `data`, not `models`. Its worker now acknowledges consumed terminal results and preserves an explicit operator test purpose. ClassScout's shared client uses resumable jobs, retains stable idempotency across transient retries, honors retry delays, exposes pending job IDs, forwards test markers and acknowledges terminal results. Interactive budgets and deterministic fallbacks stay bounded.

Protected Camera deployment/event enablement and ClassScout Production release remain subject to their repository's explicit owner-release rules. Do not claim a live event check from a local provider smoke test. Do not seed production databases or a messmass-linked event for synthetic verification.

## Capacity decision

Keep the existing CAX11/4 GB inference host, two-CPU/2800 MiB container cap, one FIFO worker and current task-specific ranked defaults. The existing second host supplies a small independent reachability check; no new paid host or resize was introduced. Successful switching and zero OOM kills do not establish a throughput SLA. Review actual production p95 queue/response timings and failures before buying capacity. Protected weights remain under top-five/14-day retention; storage targets do not authorize deleting protected models.

## Verification and rollback

Unit checks cover test/production separation, per-project isolation, fixed-column privacy, normalized routes, retention/truncation, restart persistence, idempotent admission/outcomes, acknowledgment, failure-tolerant recording, debounced alert/recovery behavior, no healthy-status mail and stable notification retries. No deliberate production outage or disk fill is needed to test the alert logic.

Deployment uses the existing idle maintenance lease, checks source hashes, validates Caddy, backs up only changed code/configuration, preserves model policy and runtime profiles, and restores the cleanup timer. Roll back the recorded observability backup as a reviewed idle update; do not delete the independent model-demand ledger or expose SQLite publicly. Stop only the watchdog unit to disable monitoring; doing so does not stop inference or Paperclip.
