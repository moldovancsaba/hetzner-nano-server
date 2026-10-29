# Narimato factory — ClassScout pilot

> **Company dashboard:** https://paperclip.haho.ai/factory. Thirteen routines now cover recovery, source freshness, support knowledge and Padel discovery. See [the current company operating guide](WORKFLOWS.md#reliable-publishing-and-portfolio-expansion--v5).

> **Current policy (28 October 2026):** eligible ClassScout new Classes listings and scoped content/contact updates now use an automatic quality gate. The former per-record human-approval description below is historical. See [the active rules, scope and live limitations](WORKFLOWS.md#evidence-branches-formats-dashboard-and-padel-africa--v4).


Paperclip: https://paperclip.haho.ai. Enter the same password as Pandora and open the Narimato company.

## Operating workflows

[All five ClassScout workflows](WORKFLOWS.md) are live: bounded catalog verification and approved contact refresh, automatic research/quality/publication handoffs, public-page audits, operating summaries and verified support drafts. Four native routines run on their Budapest schedules; the support routine presents a provider/question form on demand. [Delivery record](https://paperclip.haho.ai/NAR/issues/NAR-36).

## Use the factory

1. Create a task in **ClassScout** (the first live pilot).
2. Include one or two public, official provider page URLs in its description. State which provider facts or support question you need researched.
3. Assign **Research Analyst**, or **Support Drafter** for a draft reply, and set the task to **Todo**. Assignment wakes the agent. These roles run when assigned tasks.
4. The agent posts a draft with source links, exact evidence, missing fields and a draft reference. It assigns the task to the owner in **In review**.
5. To recheck a listing, create a task assigned to **Content Quality Reviewer** in the same project. Include `Draft reference: <reference from research comment>` in its description. Set it to **Todo**.
6. Read the evidence and approve or request changes. Approval in Paperclip does not publish into ClassScout. Complete ClassScout Classes listings can advance through the Publication Coordinator; see the publication guide.

Suggested research description:

> Research https://ymcanyc.org/locations/dodge-ymca for a ClassScout listing proposal. Capture supported name, address, phone, email, opening hours, price and activities. Keep absent facts unknown. Prepare a draft for owner review.

Projects also exist for Sportolok, Management and Padel Africa. Their source schemas and target markets need confirmation before live work. Factory Operations holds the charter and integration backlog.

## Publication

The [publication workflow](PUBLISHING.md) now takes complete ClassScout class listings through source enrichment, image preparation, human approval and the canonical publishing API. The first ready packet is NAR-26. The other research/support roles remain draft-only.

## Boundaries

The worker reads supplied pages; the Search Coordinator can also discover sources through the [budgeted Brave connection](BRAVE.md). Research/support tasks do not navigate arbitrary links, run model-generated commands, publish listings, contact customers or spend money. The separate Publication Coordinator can follow bounded relevant same-provider links and publish an exact human-approved ClassScout packet through its existing API. Dynamic pages, PDFs, login pages and sites refusing automated access may need manual research. English source extraction is the tested scope. Literal matching establishes that a quote occurs on a page; it does not independently establish that the provider's claim is true or current.

Model defaults follow the shared gateway's ranked `auto` policy, currently Granite 4 1B Hybrid with an 8K **total** context window and at most 1,024 output tokens. Each task accepts two source pages at most; long pages are reduced to bounded excerpts. This is a bounded extraction assistant, not an autonomous general-purpose researcher. The inference server is shared with chatbotapi, so queue delays affect completion times.

## Deployment and state

- Worker: `/opt/narimato-factory`, `narimato-factory.service`, loopback port 9089. DynamicUser, protected filesystem, 256 MB memory limit.
- Bridge: persistent `/opt/narimato-paperclip/data/factory/bridge.py`, invoked by Paperclip's process adapter with its per-run agent credential. No model key is placed in task text or agent output.
- Model credential: root-only `/etc/paperclip-local-ai.env`.
- Draft registry: `/var/lib/narimato-factory/factory.sqlite3`. Stores draft facts, supporting quotes, source hashes/timestamps and run outcomes; full source pages are not retained.
- Public web reads enforce public DNS/IPs, pinned connections, checked redirects, robots rules and response-size limits. Private addresses and factory hosts are rejected.
- Expected source/input errors hand the blocked task to the owner with an explicit action. Paperclip records an expected process cancellation when ownership passes to the human; verify the persisted task and confirmed reassignment rather than treating that cancellation as a failed draft. Unexpected execution failures remain failed and may need Paperclip's typed execution reconciliation before retry. Do not erase recovery holds or edit the database to force a replay.

Run tests with `python3 -m unittest discover -s paperclip/factory -p 'test_*.py'`. Live acceptance tasks use the `[Factory test]` prefix, which marks gateway inference as test traffic. Never use that prefix for ordinary business tasks.

`provision.py` is an owner-side, idempotent scaffolding command run on the Paperclip host. It preserves known project/agent IDs, enables a thirty-minute recovery heartbeat only for the Search Coordinator and requires board approval for hiring. `pilot.py` is an operator test helper, not a module to import.

Use the parent `snapshot.sh` for a restricted recovery bundle including a consistent SQLite backup. An isolated PostgreSQL backup restore passed on 28 October; a full replacement-host recovery remains untested.

Live pilot evidence and measured limits: [ACCEPTANCE.md](ACCEPTANCE.md).

First operating batch: [October 28 results](BATCH-20261028.md). ClassScout integration: [review handoff contract](CLASS-SCOUT-HANDOFF.md). The finite batch helpers create tasks and wait for review; they are not recurring jobs.

An optional, off-by-default [metered Segmind model lane](SEGMIND.md) lets the Research Analyst fill missing price and opening hours from the same public page, behind the same verbatim-quote gate and a durable spend ledger; it is deployed but switched off in production. Brave Search is connected: [usage, scheduling and safeguards](BRAVE.md). The shared broker permits one search per 30 minutes, bursts of up to three with proportionate cooldown, 48 attempts/day and at most 1,800 per provider allowance period while preserving an estimated 200 account requests. Native issue monitors resume waiting work; empty queues make no search calls. Keys stay in a root-only server environment file. Open [NAR-30](https://paperclip.haho.ai/NAR/issues/NAR-30) for dashboard instructions. See [live acceptance](brave-acceptance-20261028.json).
