# Durable source exchange

The exchange service implements the canonical OpenAPI in this directory. It transports public source evidence and outcome metadata, with exact-byte idempotency, scoped machine credentials, durable intake and fenced claim leases. It has no search, inference, catalog mutation, callback or customer-send capability. Application destination APIs remain separate release dependencies.

## Run and verify

Install requirements-runtime.txt in an isolated Python environment and run the module from this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-runtime.txt
.venv/bin/python -m exchange.server --config /etc/source-exchange/config.json
```

The private configuration must be mode 0600. config.example.json describes variable names without usable credentials. Generate independent random machine tokens; only their SHA-256 digests belong in the service configuration. The claiming principal's configured inbox UUID must match its existing private consumer database. Do not replace a lost consumer database under the old identity.

Source admission and claims are disabled unless explicitly enabled in configuration. Outcome admission, committed receipt acknowledgement, status and operation reconciliation remain separate from source admission. The process binds IPv4 loopback only and holds a singleton lease independent of any worker model lock. The systemd unit restricts network access to loopback and applies memory/task bounds. Caddy exposes only the integration route family; its existing browser gate continues protecting the factory and application.

GET status measures the caller's enrolled clients only. GET snapshot reports bounded aggregate offers, backlog and event evidence without source bodies or contact values. Unknown effort, spend or qualification instrumentation is null. The proposed public origin becomes a deployed claim only after real TLS, missing/wrong-key, scope, restart and rotation checks pass.

Run isolated transport/factory tests from the repository root:

```sh
PYTHONPATH=paperclip/integration python3 -m unittest discover -s paperclip/integration -p 'test_*.py'
```

These include lost responses, exact byte conflicts, packet deduplication, stale leases, concurrent claims, transaction rollback, private backups, source outbox atomicity, causal projection and bounded gap intents. They do not establish production destination effects or satisfy natural pilot observations.

## Factory and OpenClaw adapters

The factory source_exchange module queues a source offer in the same transaction as fetched source facts. Its existing autonomy turn sends at most a bounded outbox slice. Feature configuration is opt-in per project/scope and requires a reviewed source-policy revision. Offers default to directory-lead status until independent validation; contact values are not exported. SOURCE_EXCHANGE_MODULES identifies the installed release directory on the host. SOURCE_EXCHANGE_DASHBOARD identifies the built GDS assets.

OpenClaw owns its private connector database and worker hook in its repository. The connector saves original bytes before HTTP and commits its inbox plus receive-receipt intent before acknowledgement. Business processing and destination writes have independent controls. Do not enable either by bringing up the transport service.

The GDS dashboard source is in the adjacent dashboard directory. Its assets are served behind the existing factory browser gate. The snapshot proxy uses a server-only scoped credential and exports no key to the browser. The former company overview remains available while the integration view is commissioned.

## Recovery and rollback

Create a new consistent private snapshot, including unresolved operations:

```sh
.venv/bin/python -m exchange.manage backup --database /var/lib/source-exchange/exchange.sqlite3 --destination /private/new-exchange-backup.sqlite3
.venv/bin/python -m exchange.manage check --database /private/new-exchange-backup.sqlite3
```

A stale restore requires admission/draining off, isolated integrity and destination/quota reconciliation, and a new restore generation. The offline rotate-generation command requires a reconciliation reason and refuses to proceed while the service singleton is held. Ordinary restart preserves the generation. Never restore an older database over newer receipts or use code rollback to resurrect stale catalog writes.

Keep pending, held and uncertain messages and receipts. No retention job or backup schedule is installed by this package. Recurring off-host coverage, retention adoption and measured recovery targets remain explicit activation requirements. A local FULL-synchronous SQLite commit is not independent-host replication.
