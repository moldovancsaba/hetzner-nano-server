# ClassScout publication workflow

> **Current policy (28 October 2026):** eligible ClassScout new Classes listings and scoped content/contact updates now use an automatic quality gate. The former per-record human-approval description below is historical. See [the active rules, scope and live limitations](WORKFLOWS.md#shared-catalog-and-client-filtering--v3).


The first complete listing is ready in [NAR-26](https://paperclip.haho.ai/NAR/issues/NAR-26). Its human-only confirmation card shows the listing, timetable, source pages and prepared image. **Publish listing** approves that exact packet; **Request changes** declines it. No public record was written during preparation.

## From research to publication

1. Research an official provider page with **Research Analyst**, then recheck its draft reference with **Content Quality Reviewer**.
2. Create a ClassScout task assigned to **Publication Coordinator**, status **Todo**. Include a source-backed editorial brief in the description:

```text
Publication name: Keylab
Draft reference: <reference from the research result>
Borough: Brooklyn
Neighborhood: Carroll Gardens
Format: Classes
Activity: Music

https://www.keylab.nyc/kids-music-production-classes
```

These are plain editorial fields, not a JSON payload. The name/location/activity must occur on the supplied pages, and the draft's address/contact evidence must still match. Do not reuse Keylab's values for another provider.

3. The coordinator checks up to four same-provider pages, including relevant class/pricing/schedule links actually found on the pages. It collects explicit ages, separate class-group times/durations and a clear per-class price, prepares public copy, and sends the listing to ClassScout's existing media/review endpoint. Generic facility opening hours never satisfy a class timetable.
4. A complete result becomes an **In review** task with a human-only **Publish listing** action. The assigned coordinator remains attached so the approval can wake it automatically. No recurring heartbeat or polling automation is needed.
5. Approval resumes the coordinator. It verifies the exact payload and evidence hash, owner/issue/company binding, 48-hour expiry and unchanged source content. It checks for an existing target or another unresolved publication attempt, then calls ClassScout's canonical `publish-reviewed` endpoint. That endpoint reruns schema, duplicate and image gates against the current catalog.
6. A confirmed result posts a readable receipt and public listing link. Both private persistence and actual public-API verification must succeed; a skipped public check is not success. Final owner acknowledgment remains in review.

## Pilot scope

This first mapping supports **new ClassScout Classes listings** with explicit numerical child ages, age-specific weekday/time/duration lines and an unambiguous per-class fee. Semester/camp fees, babies' month-based schedules, ambiguous prices, other brands and other formats need their own mapping; the coordinator reports the exact missing requirement instead of inventing data. The model's seven-field research output alone is not publication-ready. The new preparation step derives program fields from source text and the editorial brief, without asking the small model to invent a full provider document.

Existing listings are held for the established improvement/owner workflow. This connector cannot overwrite them, and its ingest access is restricted in code to `provider.get`; catalog writes use only the canonical publishing endpoint. The three existing providers in the first batch still need no new listing.

## Changes and failures

Approval never covers a modified payload or evidence packet. Changing the task brief creates a fresh preparation and requires a fresh approval. If source text changed or approval expired, update the brief with a refresh note and reassign it for preparation; the old approval cannot publish the revised record. Rejected packets require a changed brief before resubmission.

A lost publishing response is recorded as **uncertain** before any retry can occur. A partial receipt is retained as **partial**, not published. The same task and another packet for the same target cannot automatically repeat an uncertain write. Inspect the existing catalog entity, source proof and receipt before operator reconciliation. Do not erase the ledger or create a fresh task to evade it.

## Runtime and credentials

- Code: `/opt/narimato-factory/publishing.py`, invoked only for the configured Publication Coordinator role and ClassScout project.
- State: `publication_packets` in the existing protected factory SQLite database. The exact outgoing payload, source proof, approval reference and receipt persist outside model context.
- Connection: root-only `/etc/paperclip-classscout.env`, loaded by `narimato-factory.service`. It contains the existing ClassScout ingest credential; no database credential was copied. Rotate it with the receiving service's credential. No secret is included in task text, model input or logs.
- Fixed receiving origin: `https://getyourfield.com`. Preparation uses `/api/content-intelligence/prepare-review`; delivery uses `/api/content-intelligence/publish-reviewed`; identity reads use only `provider.get` via `/api/ingest`.
- Official images are qualified and hosted by the existing ClassScout media pipeline. The verified canary produced an accepted R2 image. The worker does not forge media provenance or use a placeholder.
- Publication uses a separate single-slot lock from inference/research; a long local-model job does not hold the publication slot. Model inference remains unchanged at the selected 8K profile.
- The recovery archive includes the new service environment and consistent publication ledger. No full restore drill has been performed.

## Public check and ClassScout's no-em-dash rule

ClassScout rewrites every em dash on a public read (its rule 474, `src/lib/copy/emDash.ts`: "A — B" is served as "A, B"), while the private record keeps the stored text. The read-only verifier therefore compares the public record with the draft passed through `publishing.read_time_text`, a line-for-line copy of that guard; every other difference still fails, and the private record is still compared exactly. Before 2026-10-30 a draft whose name or description contained an em dash could never pass the public check: Kids Dance, Brooklyn Basement Dance Co. (NAR-566) was saved privately, stayed `partial` for a day and was finally reconciled by the factory's own recheck of a partial packet (a read-only ClassScout verification plus a guarded local status update; no catalog write). If ClassScout adds other read-time rewrites, such as its US-spelling pass, a draft containing the affected text would fail the same way and `read_time_text` needs the matching rule.

## Verification

52 tests passed locally and on the live host: approval identity/scope/hash, source or payload tampering, expiry, duplicate/owner protection, cross-packet uncertain writes, single automatic submission, partial/skipped verification, literal source mapping, class-vs-facility hours and price-unit boundaries, task cancellation and stopped executions, plus existing research/network tests.

The real Keylab preparation task ran successfully (exit 0), produced its genuine pending human confirmation, and did not create a catalog record. Its exact proposed payload passed the canonical ClassScout publish gate against the current catalog with no errors or warnings. This verification was read-only. [Acceptance evidence](publishing-acceptance.json), [canonical gate result](publishing-canonical-gate.json).

The actual live publish and subsequent public visibility remain untested until the owner approves the first real packet. The sending path and failure handling were exercised with controlled transports; no fake owner approval was applied to the real listing.
