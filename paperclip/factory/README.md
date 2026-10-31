# Narimato factory — ClassScout pilot

> **Company dashboard:** https://paperclip.haho.ai/factory. Nineteen native routines (17 scheduled, 2 on-demand forms; see `workflows.json` and the [schedule tables](WORKFLOWS.md#schedules)) cover ClassScout catalog work, recovery, source freshness, support knowledge, the Padel Africa and Sportolok engine clients and company coordination.

> **Current policy: `classscout-auto-v6`.** Eligible ClassScout new Classes and Camps listings and scoped content/contact updates use an automatic quality gate. The per-record human-approval flow described below is the mode used when the gate is switched off (`automatic_quality_gate.enabled`). See [the checks of the current gate](WORKFLOWS.md#current-automatic-quality-gate-classscout-auto-v6); open limitations are in [../README.md](../README.md#known-limitations).


Paperclip: https://paperclip.haho.ai. Enter the same password as Pandora and open the Narimato company.

## Operating workflows

[The five original ClassScout workflows](WORKFLOWS.md) are live: bounded catalog verification and contact/content refresh, automatic research/quality/publication handoffs, public-page audits, operating summaries and verified support drafts. They are part of the 19 routines above; the support routine presents a provider/question form on demand, as does the Padel source form. [Delivery record](https://paperclip.haho.ai/NAR/issues/NAR-36).

## Use the factory

1. Create a task in **ClassScout** (the first live pilot).
2. Include one or two public, official provider page URLs in its description. State which provider facts or support question you need researched.
3. Assign **Research Analyst**, or **Support Drafter** for a draft reply, and set the task to **Todo**. Assignment wakes the agent. These roles run when assigned tasks.
4. The agent posts a draft with source links, exact evidence, missing fields and a draft reference. It assigns the task to the owner in **In review**.
5. To recheck a listing, create a task assigned to **Content Quality Reviewer** in the same project. Include `Draft reference: <reference from research comment>` in its description. Set it to **Todo**.
6. Read the evidence and approve or request changes. Approval in Paperclip does not publish into ClassScout. Complete ClassScout Classes listings can advance through the Publication Coordinator; see the publication guide.

Suggested research description:

> Research https://ymcanyc.org/locations/dodge-ymca for a ClassScout listing proposal. Capture supported name, address, phone, email, opening hours, price and activities. Keep absent facts unknown. Prepare a draft for owner review.

Padel Africa and Sportolok are served through the shared Management engine's authenticated client contracts (discovery, evidence intake and maintenance; see the v6 section of [WORKFLOWS.md](WORKFLOWS.md)). Management itself is engine oversight, not a catalog. Sales Lead Generator is read-only and needs a configured workspace and scoped key ([SLG.md](SLG.md)). Factory Operations holds the charter, the coordination routines and the integration backlog.

## Publication

The [publication workflow](PUBLISHING.md) takes complete ClassScout class and camp listings through source enrichment, image preparation, the automatic quality gate (or human approval when the gate is off) and the canonical publishing API. NAR-26 (Keylab) was the first packet. The other research/support roles remain draft-only.

## Boundaries

The worker reads supplied pages; the Search Coordinator can also discover sources through the [budgeted Brave connection](BRAVE.md). Research/support tasks do not navigate arbitrary links, run model-generated commands, publish listings, contact customers or spend money. The separate Publication Coordinator can follow bounded relevant same-provider links and publish an exact packet through ClassScout's existing API once it passes the automatic quality gate (with the gate off, once it is human-approved). Dynamic pages, PDFs, login pages and sites refusing automated access may need manual research. English source extraction is the tested scope. Literal matching establishes that a quote occurs on a page; it does not independently establish that the provider's claim is true or current.

Model defaults follow the shared gateway's ranked `auto` policy, currently Granite 4 1B Hybrid with an 8K **total** context window and at most 1,024 output tokens. Each task accepts two source pages at most; long pages are reduced to bounded excerpts. This is a bounded extraction assistant, not an autonomous general-purpose researcher. The inference server is shared with chatbotapi, so queue delays affect completion times.

## Deployment and state

- Worker: `/opt/narimato-factory`, `narimato-factory.service`, loopback port 9089. DynamicUser, protected filesystem, 256 MB memory limit.
- Bridge: persistent `/opt/narimato-paperclip/data/factory/bridge.py`, invoked by Paperclip's process adapter with its per-run agent credential. No model key is placed in task text or agent output.
- Model credential: root-only `/etc/paperclip-local-ai.env`.
- Draft registry: `/var/lib/narimato-factory/factory.sqlite3`. Stores draft facts, supporting quotes, source hashes/timestamps and run outcomes; full source pages are not retained.
- Public web reads enforce public DNS/IPs, pinned connections, checked redirects, robots rules and response-size limits. Private addresses and factory hosts are rejected.
- Expected source/input errors hand the blocked task to the owner with an explicit action. Paperclip records an expected process cancellation when ownership passes to the human; verify the persisted task and confirmed reassignment rather than treating that cancellation as a failed draft. Unexpected execution failures remain failed and may need Paperclip's typed execution reconciliation before retry. Do not erase recovery holds or edit the database to force a replay.

Run tests with `python3 -m unittest discover -s paperclip/factory -p 'test_*.py'`. Live acceptance tasks use the `[Factory test]` prefix, which marks gateway inference as test traffic. Never use that prefix for ordinary business tasks.

`provision.py` is an owner-side, idempotent scaffolding command run on the Paperclip host. It preserves known project/agent IDs and every existing `factory.json` setting it does not derive from the live company (including `remote_llm`), enables a thirty-minute recovery heartbeat only for the Search Coordinator and requires board approval for hiring. `pilot.py` is an operator test helper, not a module to import.

Use the parent `snapshot.sh` for a restricted recovery bundle including a consistent SQLite backup. An isolated PostgreSQL backup restore passed on 28 October; a full replacement-host recovery remains untested.

Live pilot evidence and measured limits: [ACCEPTANCE.md](ACCEPTANCE.md).

First operating batch: [October 28 results](BATCH-20261028.md). ClassScout integration: [review handoff contract](CLASS-SCOUT-HANDOFF.md). The finite batch helpers create tasks and wait for review; they are not recurring jobs.

An optional [metered Segmind model lane](SEGMIND.md) lets the Research Analyst fill a missing name, address, price or opening hours from the same public page, behind the same verbatim-quote gate and a durable spend ledger; it is switched on in production under a $10 monthly cap, shown on the company dashboard, and it cools down if the Segmind account spends more than 120% of that cap. Brave Search is connected: [usage, scheduling and safeguards](BRAVE.md). The shared broker permits one search per 30 minutes, bursts of up to three with proportionate cooldown, 48 attempts/day and at most 1,800 per provider allowance period while preserving an estimated 200 account requests. Native issue monitors resume waiting work; empty queues make no search calls. Keys stay in a root-only server environment file. Open [NAR-30](https://paperclip.haho.ai/NAR/issues/NAR-30) for dashboard instructions. See [live acceptance](brave-acceptance-20261028.json).
