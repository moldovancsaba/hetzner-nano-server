# Improvements and outstanding verification

This lists what is still open. Items that have been finished are under "Done since the first version", each with the place that documents it. Planned model and data work is tracked in [BACKLOG.md](../BACKLOG.md).

## Still open

### Applications and evidence

- Complete each project's backend integration; set only its own production secret when authorized. Verify a request originating in the actual Vercel function. Local success is not deployment verification, and no such verification is recorded in this repository.
- Build project-specific evaluation sets (BACKLOG EV-01, EV-03). Pick workflows based on demonstrated accuracy, not model marketing or parameter count.
- Each application still needs its own request limits, prompt caps, timeouts, cancellation and graceful unavailable behavior, with no uncontrolled retries. The server's limits (see below) do not replace them; see [INTEGRATION.md](INTEGRATION.md).
- Production telemetry does not include peak container memory. Peak memory is measured only in maintenance-window benchmarks (BACKLOG EV-02); production alerts react to OOM kills after they happen.

### Reliability and access

- Add an unprivileged operator account and least-privilege sudo; test it before changing root access. Root still logs in with the key.
- Consider limiting SSH source networks or a VPN; the owner's IPv6 address can change. Maintain console recovery access. Port 22 is open to any address; key-only login and fail2ban reduce the risk but do not restrict the source.
- Independently confirm the SSH host fingerprint through Hetzner's console ([ACCESS.md](ACCESS.md) records that it has not been).
- Implement encrypted off-server backups for this host and test restoration; confirm provider backup settings and actual costs. The owner accepted running without it for now (BACKLOG OP-02).
- Add a certificate-expiry warning. The external watchdog reports an unreachable gateway only once TLS is already failing.
- Plan the Docker Engine upgrade (those packages are kept back on purpose), verify ACME certificate renewal, and keep reviewing host patches. The inference container is pinned by digest and never upgrades itself ([OPERATIONS.md](OPERATIONS.md)).
- Add per-project quotas and request-rate limiting if traffic grows. Keys now separate concurrency and permissions, but nothing limits request volume, cost or repeated bad-key attempts ([ACCESS.md](ACCESS.md)).
- Key rotation is manual and has no overlap: the gateway accepts one key per tenant, so the consumer must change at the moment of the gateway restart ([ACCESS.md](ACCESS.md#rotation)).
- Latency alerts use one 60-second p95 rule for every tenant and job type (BACKLOG OP-05); calibrate them per tenant and task.
- Known code and script limitations are listed in [OPERATIONS.md](OPERATIONS.md#known-limitations).

### Capacity and model quality

- Try a smaller model only if latency or concurrency is unacceptable; assess accuracy loss on the same data.
- Try 8 GB RAM / more CPU only after recording memory pressure, OOMs, latency and queue metrics (`GET /v1/usage`, [OBSERVABILITY.md](OBSERVABILITY.md)). Extra RAM alone does not guarantee faster generation.
- Evaluate retrieval or deterministic code for facts and simple rules instead of asking a tiny model to invent answers.
- Keep context short by selecting relevant source text; the default text profile is 8K, not unlimited chat history. Only Hungarian has been evaluated beyond English, and it did not pass its quality gate ([HUNGARIAN.md](HUNGARIAN.md)); test any other language the products use.
- Consider GPU hosting only if measured throughput/quality needs justify its cost. No GPU is present on this plan.

## Done since the first version

- Server-side limits: bounded FIFO queue, per-tenant concurrency (four queued plus running jobs, one for Paperclip), output and input caps, idempotency keys, and cancellation of queued jobs. See [JOB-ROUTER.md](JOB-ROUTER.md#queue-policy-and-resource-management).
- Separate keys and permissions per tenant, with independent revocation. See [ACCESS.md](ACCESS.md).
- Usage and failure telemetry without request content: per-project counts, queue wait, load and inference timing, errors and test/production separation. See [OBSERVABILITY.md](OBSERVABILITY.md#usage-reports).
- Service, disk, OOM, queue and failure alerts on the inference host, plus an independent reachability watchdog on the second host. Email is disabled by the owner. See [OBSERVABILITY.md](OBSERVABILITY.md#watchdogs-and-notification-delivery).
- Key-only SSH with fail2ban on both hosts. See [ACCESS.md](ACCESS.md#key-only-ssh-and-fail2ban-owner-decision-2026-10-30).
- Inference stays bound to loopback (`config/compose.yaml`); apart from SSH, only Caddy listens publicly. See [OPERATIONS.md](OPERATIONS.md).
- Host patching and a reboot test with services verified afterward. See [HISTORY.md](HISTORY.md).
- Backups and a restore drill for the Paperclip host (`paperclip/backup.py`, `paperclip/restore-drill.py`); a full replacement-host recovery there is still untested. See [paperclip/README.md](../paperclip/README.md).
- Larger default context with token budgeting, and a separate experimental Hungarian job. See [CHATBOT-CONTEXT.md](CHATBOT-CONTEXT.md) and [HUNGARIAN.md](HUNGARIAN.md).

## Deliberate limits of this setup

No GPU, no high availability, no load balancer, no proven production SLA, no backup or restore drill for this host, no tested high concurrency, no automatic credential rotation, no recorded verification from a deployed Vercel function, and no production model-quality acceptance. Monitoring exists but is small: one private watchdog and one independent reachability check. The public API covers models, chat, jobs, queue, usage and moderation jobs; model management and the native Ollama API are not exposed and must use SSH.
