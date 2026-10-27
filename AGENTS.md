# Agent instructions for the Hetzner workspace

Read README.md first, then the guide for your task. Server access and credentials are authorized resources for the owner's requested work, not authorization to deploy unrelated projects or perform destructive changes.

- Inspect current server state and changes by other agents before editing.
- Read project keys from private/api-keys.json programmatically; never print them. Use exactly the intended project key.
- Never copy the SSH private key into this folder. Ask the owner to unlock it locally if necessary.
- Keep private/ excluded from Git and any shared artifacts. Live Caddy config contains keys too.
- Keep inference on loopback. Validate Caddy/Compose changes before applying them.
- Use scripts/healthcheck.py for authentication checks; scripts/benchmark.py is a low-volume synthetic evaluation, not a load test.
- Do not treat valid JSON as correct output. Read docs/MEASUREMENT.md before selecting production workflows.
- Record changes, measured outcomes and limitations in the relevant docs. Refresh config snapshots after deployment, redacting credentials in public copies.
- Follow each application repository's own instructions when touching it. Do not change Vercel Production configuration or publish releases merely because local server access works.
- No external messages, recurring monitoring, bulk stress tests, destructive volume removal, or server deletion are implicit in documentation maintenance.

## Independent capability evaluation

English chat, English structured tasks, image analytics, and non-English capabilities are separate workstreams. Never penalize or approve an English model based on non-English results, or average languages into a combined score. Keep non-English evidence in benchmarks/non-english/, with per-language and per-task approval. English OCR does not establish other-language OCR. Read that workstream’s report before any language-specific routing change.

## Ranking-driven default services (owner directive 2026-10-27)

Default jobs must always follow the best eligible model in their current task-specific ranking. Read docs/MODEL-POLICY.md. Every new test round is unfinished until ranking sources, generated config/model-policy.json, installed winning artifacts, deployed policy, API discovery, actual auto jobs and documentation agree. Run scripts/promote_rankings.py --write and --check; do not maintain hard-coded defaults elsewhere or leave the previous winner active. Keep moderation separate from general image ranking and all non-English scores separate. Explicit client model IDs are real deliberate overrides, never secretly remapped; default clients use auto. Only installed, successfully tested matching digests are selectable; list other installed packages as blocked. Never expose public model installation/management or publish secrets.

## Continuous research and retention (owner directive 2026-10-27)

Read BACKLOG.md, docs/CONTINUOUS-EVALUATION.md and docs/DATA-RETENTION.md. The daily server discovery job is metadata-only: no automatic weight downloads, inference, default changes or external notifications. Keep known/declined model metadata, digests and evidence even when deleting binaries; rebuild/deploy config/tested-models.json after every test round. Do not repeat an unchanged failed model without a changed-condition reason.

Never capture live Camera images or conversations for training. Only curated, explicitly approved datasets and labels may be retained for training, with provenance/approval/version/split/deletion manifests. Keep training and held-out evaluation separate; do not place private datasets in public Git. Gateway request bodies are RAM-only; terminal results expire after 300 seconds or client DELETE. Do not introduce body logging, durable payload storage, or training export through an unrelated change. Keep defaults, approved client pins and rollback weights protected when cleaning cache; declined weight deletion must preserve metadata and refuse active/protected packages.

## Automatic model retention (owner directive 2026-10-27; supersedes static pins)

Read docs/AUTO-MODEL-CLEANUP.md. Retain installed top five per task ranking plus models with admitted non-test inference demand in the last 14 days. This replaces earlier permanent alternative pins and seven-day rollback-cache policy; defaults and active/queued work remain protected, and pre-tracking inventory gets a one-time 14-day history grace. Metadata, test evidence, approved training data and labels are never cleaner targets.

Every benchmark, smoke test, operator verification and automated UI test must send X-Request-Purpose: test through the gateway (Pandora forwards the marker). Native benchmarks do not count as production use. Never manufacture production traffic to keep a model. Pause the cleanup timer before temporary/native model experiments, drain service work, then restore/verify and re-enable the timer. Cleanup requires the gateway maintenance lease; do not bypass it with Docker removal scripts or delete/alter the usage ledger to force eviction.
