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
