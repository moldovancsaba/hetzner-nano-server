# ClassScout publication workflow

> **Current policy: `classscout-auto-v6`.** Eligible ClassScout new Classes and Camps listings and scoped content/contact updates use an automatic quality gate. The per-record human-approval flow described below is the mode used when the gate is switched off (`automatic_quality_gate.enabled`); steps 4 and 5 and the approval wording apply to that mode. See [the checks of the current gate](WORKFLOWS.md#current-automatic-quality-gate-classscout-auto-v6).


In human-approval mode the confirmation card shows the listing, timetable, source pages and prepared image. **Publish listing** approves that exact packet; **Request changes** declines it. No public record is written during preparation. The first complete listing, [NAR-26](https://paperclip.haho.ai/NAR/issues/NAR-26) (Keylab), was prepared this way and was later saved and verified under the automatic policy.

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
4. In human-approval mode a complete result becomes an **In review** task with a human-only **Publish listing** action. The assigned coordinator remains attached so the approval can wake it automatically. No recurring heartbeat or polling automation is needed. With the gate on, no card is created: the same run goes straight to the automatic checks and, if they all pass, to publication.
5. In human-approval mode, approval resumes the coordinator; with the gate on it simply continues. It verifies the exact payload and evidence hash, owner/issue/company binding, 48-hour expiry and unchanged source content. It checks for an existing target or another unresolved publication attempt, then calls ClassScout's canonical `publish-reviewed` endpoint. That endpoint reruns schema, duplicate and image gates against the current catalog.
6. A confirmed result posts a readable receipt and public listing link. Both private persistence and actual public-API verification must succeed; a skipped public check is not success. Final owner acknowledgment remains in review.

## Pilot scope

The mapping supports **new ClassScout listings** in two formats (`formats.py`): Classes with explicit child ages (years or months, including halves and number words), age-specific weekday/time/duration lines and one unambiguous stated fee per class, month, term or semester (an unknown price is recorded as unknown, never as free); and dated Camps with one future ISO date range, a timetable and a stated day, week or session fee. Ambiguous prices, other brands and other formats need their own mapping; the coordinator reports the exact missing requirement instead of inventing data. The model's seven-field research output alone is not publication-ready. The new preparation step derives program fields from source text and the editorial brief, without asking the small model to invent a full provider document.

Existing listings are held for the established improvement/owner workflow. This connector cannot overwrite them, and its ingest access is restricted in code to `provider.get`; catalog writes use only the canonical publishing endpoint. The three existing providers in the first batch still need no new listing.

## Changes and failures

Approval never covers a modified payload or evidence packet. Changing the task brief creates a fresh preparation and requires a fresh approval. If source text changed or approval expired, update the brief with a refresh note and reassign it for preparation; the old approval cannot publish the revised record. Rejected packets require a changed brief before resubmission.

A lost publishing response is recorded as **uncertain** before any retry can occur. A partial receipt is retained as **partial**, not published. The same task and another packet for the same target cannot automatically repeat an uncertain write. Inspect the existing catalog entity, source proof and receipt before operator reconciliation. Do not erase the ledger or create a fresh task to evade it.

## Runtime and credentials

- Code: `/opt/narimato-factory/publishing.py`, invoked only for the configured Publication Coordinator role and ClassScout project.
- State: `publication_packets` in the existing protected factory SQLite database. The exact outgoing payload, source proof, approval reference and receipt persist outside model context.
- Connection: root-only `/etc/paperclip-classscout.env`, loaded by `narimato-factory.service`. It contains the existing ClassScout ingest credential; no database credential was copied. Rotate it with the receiving service's credential. No secret is included in task text, model input or logs.
- Fixed receiving origin: `https://classscout.ai` (`publishing.ClassScout.BASE`; the shared catalog, moved from getyourfield.com in the v3 policy). Preparation uses `/api/content-intelligence/prepare-review`; delivery uses `/api/content-intelligence/publish-reviewed`; identity reads use only `provider.get` via `/api/ingest`.
- Official images are qualified and hosted by the existing ClassScout media pipeline. The verified canary produced an accepted R2 image. The worker does not forge media provenance. When no official image qualifies, the only placeholder it accepts is ClassScout's own hosted category banner, marked as such in the packet (see "A missing image is not a blocker" below).
- Publication uses a separate single-slot lock from inference/research; a long local-model job does not hold the publication slot. Model inference remains unchanged at the selected 8K profile.
- The recovery archive includes the new service environment and consistent publication ledger. An isolated full-application restore drill (`restore-drill.py`) has since passed (see [WORKFLOWS.md](WORKFLOWS.md)); real host replacement has not been exercised. The Segmind key file is part of the recovery bundle.

## Source, age, name and contact checks (2026-10-30)

A delivery review found drafts held for reasons that were format gaps, and two kinds of wrong brief that the gate would have let through. All are deterministic and fail closed.

- **Stated ages** (`formats.ages`) accept "ages 5-12", "aged 4 to 11", "ages 3 through 6", number words ("ages three to ten") and halves ("ages 2.5-3.5", kept exact in months). They still refuse an open range ("3 and up"), school grades, words such as "toddlers" or "teen", and anything above 17 years 11 months.
- **Phone numbers** in the `official_contacts` check compare by digits without a leading US country code, because the draft carries `+17184478667` and the page says `718-447-8667`. Website and email still compare as before, and a different digit, an extension or a missing number is still a hold.
- **Third-party lists and directories** (`publishing.LISTING_HOSTS`, for example newyorkfamily.com, yelp.com, facebook.com) cannot become a provider listing. The brief step names it as the gap and never sends such a page to the model.
- **Borough against address.** If the verified address names a borough (Brooklyn, Queens, Bronx, Staten Island, Manhattan), the brief's borough must be the same one.
- **Name.** A publication name containing `|` is a page title, not a provider name, and is held until a clean name exists.

## A missing image is not a blocker (owner decision 2026-10-30)

ClassScout's own rule is that a missing official image is maintenance debt, not a publish blocker; it applied only to persisted content cards. The preparation call now sends `workflowMetadata.allowCategoryBannerFallback: true`, and sends no image request when the pages offer no image candidate. When no official image qualifies, ClassScout returns its own hosted category banner (an `i.ibb.co` URL carrying the diagnostic `content_card_category_banner_fallback`) and the listing publishes on it.

The factory accepts that banner only as a marked placeholder. `publishing.category_banner` requires a ready, accepted media result, the diagnostic and the `i.ibb.co` host; the packet proof then carries `image_placeholder: true`, which `quality_gate.qualified_media` needs before it accepts a result whose source image is not one of the page's candidates. The review text says the listing uses a category banner. Every other check is unchanged, and a media result that is neither an official candidate nor ClassScout's banner is still refused.

This depends on the ClassScout change that reads the new option (`prepareReviewPacket.ts`), which went live on 2026-10-30 (see [docs/HISTORY.md](../../docs/HISTORY.md)). Before it, ClassScout ignored the option and a listing without a usable image was held, with ClassScout's own reason.

## Public check and ClassScout's no-em-dash rule

ClassScout rewrites every em dash on a public read (its rule 474, `src/lib/copy/emDash.ts`: "A — B" is served as "A, B"), while the private record keeps the stored text. The read-only verifier therefore compares the public record with the draft passed through `publishing.read_time_text`, a line-for-line copy of that guard; every other difference still fails, and the private record is still compared exactly. Before 2026-10-30 a draft whose name or description contained an em dash could never pass the public check: Kids Dance, Brooklyn Basement Dance Co. (NAR-566) was saved privately, stayed `partial` for a day and was finally reconciled by the factory's own recheck of a partial packet (a read-only ClassScout verification plus a guarded local status update; no catalog write). If ClassScout adds other read-time rewrites, such as its US-spelling pass, a draft containing the affected text would fail the same way and `read_time_text` needs the matching rule.

## Verification

At the time of the first rollout, 52 tests passed locally and on the live host (the factory suite has grown since): approval identity/scope/hash, source or payload tampering, expiry, duplicate/owner protection, cross-packet uncertain writes, single automatic submission, partial/skipped verification, literal source mapping, class-vs-facility hours and price-unit boundaries, task cancellation and stopped executions, plus existing research/network tests.

The real Keylab preparation task ran successfully (exit 0), produced its genuine pending human confirmation, and did not create a catalog record. Its exact proposed payload passed the canonical ClassScout publish gate against the current catalog with no errors or warnings. This verification was read-only. [Acceptance evidence](publishing-acceptance.json), [canonical gate result](publishing-canonical-gate.json).

That record describes the first rollout: the live publish and public visibility were then untested. Later listings were saved and verified privately and publicly (for example NAR-160 in [WORKFLOWS.md](WORKFLOWS.md)). The sending path and failure handling were exercised with controlled transports; no fake owner approval was applied to the real listing.
