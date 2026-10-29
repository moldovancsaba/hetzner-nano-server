# Budgeted Brave Search

Brave is connected to the Paperclip host through a server-only Search Coordinator. Initial scope is ClassScout. Other roles still use source pages directly where possible. Search does not replace evidence checks or human publishing approval.

## Use it from the dashboard

Create a ClassScout task assigned to **Search Coordinator**, status **Todo**:

```text
Search purpose: publishing
Search query: site:provider.example kids classes pricing schedule
Source host: provider.example
```

Use `discovery` for new providers or `support` for public provider information. `Source host` is optional for discovery; include it when researching a known provider. Queries must contain public business/location/activity terms, not customer emails, phone numbers, credentials or private conversation text. One task can contain up to three distinct `Search query:` lines; those form a burst that borrows future slots. Reuse existing sources before requesting another search.

The coordinator fetches eligible result pages independently and creates at most **two research tasks per search job** in the initial rollout (hard implementation ceiling five). Research tasks trigger their own Content Quality Reviewer tasks. Candidates remain provisional: source-url duplication is filtered early; physical identity and duplicates are checked during research and by the canonical publishing gate. Different branches on the same domain are not merged.

Publication preparation automatically queues a targeted search when it lacks explicit ages, class times, per-class price or a usable source image. Verified new pages may restart only an unchanged, still-blocked, unapproved parent publication task. Prepared/approved/uncertain/published packets are never silently modified. A refreshed packet still requires a fresh human publishing approval. The current publishing mapper's supported-format boundaries remain in force; search does not convert semester fees into per-class fees.

## Budget and scheduling

| Burst | Request spacing | Cooldown after the last response |
| --- | --- | --- |
| One query | — | 30 minutes |
| Two queries | At least two seconds | 60 minutes |
| Three queries | At least two seconds | 90 minutes |

All roles/brands/keys using this factory share the same SQLite ledger. Limits: 48 reserved attempts per Budapest day, 1,800 per observed provider billing window, and a protected estimated account balance of 200. The user plan's total is 2,000/month and one request/second. Unsent reservations after a crash and uncertain attempts stay conservatively counted. The original one-request credential probe is included.

The ledger reads Brave's rate-limit policy, remaining and reset headers. It never refunds local usage from an optimistic/lagging header. Other consumers of this Brave account must share this broker or be accounted for; quota headers cannot prevent an unrelated application from spending outside the broker.

Cooldowns and reservations survive restarts. Requests crossing a billing/day boundary are checked again. Each queued wait records an explicit Paperclip **issue monitor** at its next eligible deadline; a thirty-minute native Search Coordinator heartbeat is a recovery/checking mechanism, not permission to query every five minutes. Empty queues make no Brave calls. Quota waits never trigger rapid retries. New discovery pauses when ten research drafts/tasks await work or review; publishing work has priority over discovery, then support. Exhausted account quota waits until the provider reset. Transient failures permit at most two job attempts with the same budget/cooldown; authentication/configuration failures require attention.

## Retention and credentials

- Root-only secret: `/etc/paperclip-brave.env`, read by `narimato-factory.service`. It is not passed to model prompts, agent process environments, browser code or issue text.
- Fixed endpoint: `https://api.search.brave.com/res/v1/web/search`, web results only, English/US, strict safe search, count 20, extra snippets enabled, no automatic pagination or redirects.
- Brave response bodies, snippets and result titles remain in RAM. Persistent result caching is disabled until storage rights for this account's plan are confirmed.
- Durable data consists of our query intents/fingerprints, task links, quota audit metadata, and independently fetched source-page URLs/titles/hashes. No raw customer chat is sent to search or retained for training.
- Tables: `search_account`, `search_attempts`, `search_jobs` in the existing protected factory SQLite database. Seven-day intent deduplication prevents repeated searches; direct-source evidence follows the normal factory policy.
- Local health/status: `GET http://127.0.0.1:9089/search/status`. It exposes budget/queue metadata, never the key. Human-readable usage and the next eligible time appear in search task comments in Budapest time.
- The restricted recovery bundle includes the new environment file and consistent ledger snapshot. Do not restore an old ledger over newer usage; reconcile provider headers and conservative reservations first.

## Verification

Budget tests cover concurrent reservation, restart, burst debt/response timing, per-second spacing, daily/monthly caps, account reserve, external usage headers, header lag, uncertain responses and quota rollover. Workflow tests cover intent deduplication, backpressure, source-host checks, direct-source-only evidence retention, protected publication parents, query privacy and no retry loop on HTTP 429. See the dated live acceptance record for the total suite count and actual pilot outcome.

The first cooldown test exposed Paperclip's liveness rule: an in-progress task without a durable wait target is treated as stalled. The coordinator now records a native issue monitor and returns the task to review while retaining the assigned coordinator. The original pilot was restored through the official recovery-action API; no quota or cooldown was reset and no database recovery hold was erased.

Source research and support can wait through temporary shared-model storage maintenance using five-minute native issue monitors, up to twelve waits. Retry identity, attempt count and deadline live in the factory `model_waits` ledger because Paperclip consumes a monitor before dispatching its agent. A consumed monitor is not used as proof that work has already finished. Successful source work clears the wait record. This does not retry publication writes or issue Brave requests. The first STREB research executions were rejected by a concurrent model benchmark before inference and then cancelled during handoff; their recovery records remain intact. Replacement source-only tasks NAR-31/NAR-32 use the new bounded wait. See the dated acceptance record for their current stage.

Maintenance on 28 October corrected the consumed-monitor resume path. NAR-31/NAR-32 resumed through real native scheduled callbacks and both completed extraction; automatic quality reviews NAR-33/NAR-34 followed. The Kids draft passed source checks; the camp draft needs an explicit provider name. These are source drafts, not complete approved ClassScout publication packets. Search usage remained two requests, including the original probe. See [maintenance results](maintenance-20261028.json).
