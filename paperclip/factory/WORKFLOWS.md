# ClassScout operating workflows

The five workflows are live in [Paperclip](https://paperclip.haho.ai). Open **Routines** to see the four schedules and the support form. They use the existing five employees. Open [the delivery record](https://paperclip.haho.ai/NAR/issues/NAR-36) for results and task links.

## Schedules

All times use Europe/Budapest, including daylight saving changes.

| Work | Schedule | Employee | Output |
| --- | --- | --- | --- |
| Verify existing listings | Daily at 08:00 | Content Quality Reviewer | Up to three canonical records checked against official sources; evidence gaps can create bounded research tasks |
| Prepare complete listings | Daily at 08:45, plus after successful quality review | Publication Coordinator | Complete briefs advance to preparation; existing pending packets are reused |
| Audit public pages | Monday at 08:30 | Content Quality Reviewer | Bounded HTTP/HTML metadata report and deduplicated follow-up tasks for significant findings |
| Summarize operations | Daily at 09:00 | Support Drafter | Review items, blocked work, quality states, catalog checks, website findings and shared search allowance |
| Draft a support reply | When you submit a question | Support Drafter | A sourced reply for review or a clear escalation |

Schedules skip missed occurrences after downtime and skip a new occurrence while the previous routine issue is still open. Completed reports close their own routine issue; human approvals and support drafts remain separate review items. The support form accepts separate questions even while earlier replies await review. None of these routines spends Brave requests merely because a timer fires.

## Verify and refresh existing listings

The scheduled check reads one paginated NYC catalog page with a maximum of twenty cards, selects up to three records and reads each exact canonical record. It rotates through the page and moves forward on later runs. It does not download the entire catalog. Owner-managed records stay in their existing owner workflow.

The worker re-fetches the official page and checks the retained name, street address, phone and email. A catalog value absent from that page is an evidence gap, not proof that the value is incorrect. Missing evidence can create at most two Research Analyst tasks per batch, with new research held when ten research tasks/drafts await work or review. Querying a known official page does not use Brave.

Research automatically triggers quality review. When a source draft passes and identifies an existing provider, a contact correction can advance to the Publication Coordinator. Corrections cover **phone and email only** in this rollout. Price, timetable, category, name, address and ownership are never silently rewritten by this contact path.

A correction card shows the exact old and proposed values. **Apply correction** approves that exact packet for 48 hours. Before sending it, the coordinator checks the human identity, packet integrity, current catalog baseline, ownership, active execution and unchanged source. The canonical ClassScout API validates the patch. A successful result must then agree in both the private record and public catalog. Lost or partial responses are held for reconciliation and never automatically resubmitted.

Matching contacts are a successful no-op. There is no reason to write a record merely to make the factory look active. A source check's date is stored in the factory; it does not certify every program field or rewrite the catalog's verification date.

For a focused check, create a ClassScout task assigned to Content Quality Reviewer:

```text
Factory workflow: verify_catalog
Catalog IDs: prov-tinyout-brooklyn-music-factory
```

## Prepare complete listings

For a new listing, create a ClassScout task assigned to Research Analyst. Include one or two official pages and source-supported editorial fields:

```text
Factory workflow: source_research
Publication name: Keylab
Borough: Brooklyn
Neighborhood: Carroll Gardens
Format: Classes
Activity: Music

https://www.keylab.nyc/kids-music-production-classes
```

The example reuses the existing Keylab review; use the actual name and location for a different provider. Research triggers quality review. Passing drafts with complete editorial fields advance to publication preparation automatically, and the daily preparation routine picks up eligible drafts as well. An unresolved packet for the same source and matching brief is linked instead of creating another approval.

The preparation step still requires explicit child ages, a class timetable and duration, an unambiguous per-class fee, accepted media and the canonical schema. Missing information stays a gap. The initial mapping supports new **Classes** listings; camps, semester fees and other formats require their proper mapping. See [publication details](PUBLISHING.md).

**Publish listing** is the human approval that permits the exact prepared packet to be sent. The coordinator rechecks sources, expiry and duplicate conditions before calling ClassScout, and requires verified private and public receipts before claiming publication. Expired or changed packets require fresh preparation and a new approval. The existing [Keylab packet](https://paperclip.haho.ai/NAR/issues/NAR-26) remains pending; this rollout did not approve it.

## Audit public pages

The weekly audit starts from the three pages verified during rollout: the homepage, NYC Classes and NYC Family Events. It can follow actually observed public links up to a six-page limit, with an implementation ceiling of eight. It checks response status, titles, descriptions and canonical metadata, and respects automated-access rules and response-size limits.

Significant findings create at most five deduplicated follow-up tasks per run. Repeated observations link the existing task. A finding no longer observed on a successful HTML check is marked as not reproduced in the audit ledger; this does not pretend that someone fixed the site.

This is an HTTP/HTML audit. Browser usability, JavaScript rendering, search indexing, ranking and security require their own tests. The audit does not deploy changes to ClassScout.

For a focused audit, assign Content Quality Reviewer:

```text
Factory workflow: audit_site
Audit URLs: https://getyourfield.com/nyc/classes
```

## Read the operating summary

Open the **Summarize ClassScout operations** routine and its latest run. The summary uses actual Paperclip issue states and factory ledgers. It distinguishes source drafts, prepared publication packets, contact corrections and confirmed writes. Counts and summaries use code; they do not spend model tokens.

Read an idle employee together with the task state: completed work, pending human review and a maintained scheduled wait are normal. A blocked issue, missing source or uncertain write has its own action. The summary links pending decisions and reports the shared Brave allowance without exposing the key or copying customer questions.

## Draft support replies

Open **Routines → Draft a ClassScout reply → Run now** and enter the provider name or ClassScout listing link, and the question. Names resolve only to a uniquely verified catalog record. For an unverified name or a provider with multiple branches, paste its ClassScout listing link into the form; a normal task can also include the street address.

A normal task can use:

```text
Factory workflow: support_answer
Provider name: Brooklyn Music Factory
Question: What phone and email can I use to contact this provider?
```

Or replace `Provider name` with `Listing URL: <the public ClassScout listing link>`. Internally identified records can also use `Catalog provider`.

The worker rechecks the official page and includes only current, literal evidence. A reply states its source and check time. Unsupported facts stay unknown. Bookings, refunds, payments, customer accounts, current class availability and schedules escalate to a person; facility opening hours never establish class availability.

The result is a **draft**. Review it and send it through your normal support channel if appropriate. No customer inbox or outbound delivery connection is enabled by this workflow. Customer questions are not sent to Brave or used for training; the factory's extra report stores the public answer/evidence, not the raw question.

## Operations and recovery

Implementation: `catalog.py`, `refresh.py`, `pipeline.py`, `site_audit.py`, `operations_digest.py`, `support.py` and the fixed role router `operational.py`, invoked by the existing process bridge. Read-only operational work has its own bounded slot so it can proceed while source inference occupies the model slot. Publication and search retain separate slots; the shared inference gateway still admits one active model job.

Configuration is in `factory.json`; native routine/trigger IDs and civil schedules are in `workflows.json`. `workflows_setup.py --activate` is an owner-side idempotent setup command. It checks an existing routine's purpose and assignment before updating it. It does not approve publication or contact corrections. Native routine timers are on the server, independent of an open browser or this conversation.

The factory stores public evidence and operational state in its existing protected SQLite database. New tables cover catalog checks/cursor, workflow reports, pipeline links, contact packets and website findings. Keys remain in root-only environment files, outside task descriptions and model context. Keep the quota and publication ledgers when restoring; never use an old snapshot to repeat a write or reset allowance.

Acceptance: [dated results](workflows-acceptance-20261028.json). The full factory suite covers approval identity, expiry, changed baselines and sources, uncertain writes, bounded reads, duplicate findings, grounded support, escalation, question-field injection and automatic handoffs. Live tests used real reads and native routine runs; catalog writes and customer delivery were not faked as successful outcomes.

## Automatic publication and content policy — 28 October 2026

> Historical v2 policy: superseded by **Shared catalog and client filtering — v3** below. Client display filters must never block shared catalog collection.

This section supersedes the per-record human-approval instructions above. The owner authorized eligible writes through an automatic quality gate. The active policy is `classscout-auto-v2`, enabled for ClassScout only, with ten combined publication/update attempts per Budapest calendar day. Other projects retain their current behavior until their own canonical adapters and field rules are validated. Customer replies remain drafts; this instruction authorizes catalog publication and content updates, not customer delivery.

A new **Classes** listing must pass independent source review, fresh official-source checks, deterministic copy comparison, explicit age bounds, age-specific class timetable/duration, an unambiguous per-class price, grounded contacts and activity, qualified official-image provenance, no existing target, current ClassScout public visibility settings, and the receiving application's final schema/duplicate/image gate. Every required check must pass; a model confidence score cannot authorize a write. A catalog save plus matching private and public verification establishes publication. Disabled activities/categories/regions are held before writing. The factory does not change site settings to make a listing visible.

Existing unclaimed listings can receive literal source-supported phone/email corrections. Missing short/long descriptions can be filled with neutral copy whose name, location and activities occur on the current official page. The factory can refresh descriptions previously generated by this update workflow when the current value still matches its own saved prior output. Existing editorial copy is preserved. This first policy does **not** automatically change existing names, addresses, ownership, images, prices, ages, program schedules or arbitrary editorial copy. Those fields need dedicated update mappings and evidence gates; new-listing completeness checks do not authorize arbitrary existing-record patches.

The daily catalog routine requests at most two research/quality chains per three-record batch, with a seven-day refresh interval and a backlog limit. Successful research and quality handoffs close automatically; eligible writes complete automatically. The publication queue reuses and resumes held/prepared listing packets. A policy hold does not spend a Brave request or manufacture a human approval. Unsupported/conflicting facts remain exceptions. Pending human rejections/withdrawals are respected.

Exact outgoing packets, baseline values, source proofs, gate decisions, policy versions, submission reservations and receipts persist in SQLite. The daily attempt reservation and packet transition share a transaction. Claimed listings, stopped tasks, changed briefs/baselines/sources and unresolved writes cannot be silently overwritten. Lost responses and partial writes are never automatically submitted again. Their verification/reconciliation is read-only. A confirmed save hidden by site settings is recorded separately as `saved_hidden`, not publicly published.

### Live acceptance

145 tests passed locally and on the server, including automatic submission without a fabricated approval, single submission, invented copy, source changes, image qualification, exact class schedules/ages, ownership, daily quotas, disabled activities/regions/categories, and read-only visibility reconciliation.

Keylab (NAR-26) passed the first live gate and ClassScout's final canonical gate, and was saved once as `prov-keylab`. Its private record matches the prepared content. Its public lookup returned 404 because runtime settings `g17.c12.d9.dc2` disable **Music**. The record was reconciled to `saved_hidden` without another write. This exposed the missing visibility preflight, now required by v2. No public success or browser visibility is claimed for Keylab. No Music setting was changed. Actual public publication under v2 and actual contact/content changes still require an eligible live case; those sending and failure paths passed controlled transport tests.

### Disable or recover

Set `automatic_quality_gate.enabled` to false in `/opt/narimato-factory/factory.json`; subsequent eligible work returns to exact human review. Preserve all ledgers and receipts. The pre-change archive and restricted code/config backups are under `/root/paperclip-backups`. Reverting code does not undo a catalog write. Baselines and exact patches support a separately checked corrective action; never replay an uncertain write or restore an old database over newer work merely to roll back code.


## Shared catalog and client filtering — v3

Owner correction, 28 October 2026: **ClassScout is the shared catalog. GetYourField and other clients choose their own display filters.** Music, Art, STEM and other supported activities are eligible for evidence-backed catalog intake regardless of a client's enabled categories. All source, age, class schedule, price-unit, media, duplicate and ownership checks remain in effect. The current Classes mapping still requires the documented program evidence; changing the activity policy does not imply support for every listing format.

The active automatic policy is `classscout-auto-v3`. Machine preparation/publication, authenticated per-ID catalog reads, bounded catalog discovery and contact/content update verification now use `https://classscout.ai`. Client site audits can continue to inspect GetYourField. Both client and core listing links resolve to the shared catalog ID. Neither global nor client runtime settings were modified.

Root cause: the earlier worker used GetYourField as the integration origin, then incorrectly added its product-specific display settings to shared catalog eligibility. The application itself already separates these concerns: its domain registry describes one deployment and database; runtime settings merge global, city, domain and domain-city scopes, and public reads apply the current request's domain settings. The authenticated canonical publish/ingest paths write the shared collections. ClassScout's existing live settings enable Music, Art and STEM. GetYourField deliberately filters those activities out for its sports-focused product.

Live Keylab evidence: `classscout.ai/api/public/providers/prov-keylab?city=nyc` returns **200**, while the same request to `getyourfield.com` returns **404**, as expected for that client. The complete private catalog record matches the prepared draft. A bounded per-ID ClassScout public read matches identity, location and descriptions. The worker reconciles the old `saved_hidden` state to **published in ClassScout** through reads only, preserving the original client-side partial receipt and adding an explicit core catalog verification receipt. No second submission is made. A missing or mismatched core read cannot establish success or trigger a repeat write.

152 tests passed locally and on the live server, including client-hidden Music being eligible for catalog intake, catalog verification origin, exact private field matching, public identity mismatch, missing verification, and read-only reconciliation without resubmission. The ClassScout application and Vercel configuration were not changed.

## Production growth mode — 28 October 2026

The owner requested full production throughput. Growth mode is now enabled for the validated **ClassScout NYC** integration. Other brands remain gated on their own source schemas and publishing adapters. ClassScout catalog intake stays independent of client display filters.

- Discovery dispatch: every 30 minutes, rotating 360 public search intents across all five NYC boroughs, 12 activity groups and six program/pricing/schedule search angles. This is an opportunity to work, not a promise to spend a request: shared cooldown, seven-day intent deduplication, ten production research tasks/drafts and at most two pending search jobs constrain dispatch. Old `[Factory test]` drafts no longer consume production discovery capacity.
- Brave: unchanged one shared request per 30-minute slot, maximum 48/day, 1,800/provider allowance period, protected reserve 200. Publication-blocking searches keep priority. Up to three independently fetched source pages per discovery query; sources from ClassScout/GetYourField themselves are excluded from official-provider discovery evidence. No Brave response/snippet cache was introduced.
- Existing catalog verification: hourly, three records per run, at most two downstream research tasks. Approximately 72 records/day is the scheduled ceiling, not a guaranteed successful verification count. Source failures, ownership, stale evidence and backlog holds still constrain work.
- Publication preparation: every half-hour at :15 and :45. A rotating five-draft batch avoids repeatedly processing only the newest items. Production scans exclude synthetic source tasks. A verified campaign source can supply its own editorial brief only when the current official page supports one provider name/address, the campaign activity/borough, Classes, and exactly one canonical neighborhood. Query terms alone are never evidence. Missing or ambiguous metadata remains held. Program times, numerical ages, price units and media still pass the complete existing publication gate.
- Qualified writes: up to **20 combined new-listing/contact/content write attempts per Budapest day**. A daily-cap hold receives a native next-day 00:05 Budapest deadline, then rechecks the exact evidence and packet. Lost/partial writes are never replayed. Existing update field scope remains phone/email and the documented missing/factory-generated descriptions, not arbitrary price/schedule/editorial changes.
- Site audit: daily at 08:30, retaining the bounded GetYourField client audit. Operations digest: daily at 09:00. Support remains on demand and draft-only.

All schedules use Europe/Budapest, skip missed slots and avoid overlapping runs of the same routine. The existing five roles and tested 8K inference profile are retained. Local model calls remain serialized through the shared scheduler; no extra model instance, memory allocation, provider plan, or infrastructure purchase was introduced.

165 tests passed locally and on the server. The live native discovery, catalog and publication routines were started immediately: NAR-52 dispatched the first production campaign, NAR-55 began Brooklyn Music discovery, and NAR-56/NAR-57 began existing-provider research for Wild Heart Performing Arts Studio and Fancy Feet Dance. The first production query increased the durable Brave count from two to three and persisted its cooldown. These are genuine company tasks, not load tests or synthetic traffic. Source/review/write outcomes are reported separately; no new publication count is inferred from a successful search.

To reduce volume, disable `growth_mode.enabled` and rerun `workflows_setup.py --activate`: the original schedules return. The growth routine must also be paused in Paperclip when disabling growth mode, because it is deliberately not deleted. Disabling growth mode does not cancel already created tasks or undo catalog writes. Automatic publication has its separate enable switch and durable submission ledger.


Growth-mode live routing correction: catalog coordination runs under the existing operations/support role, followed by Research → independent Quality → Publication. This avoids Paperclip's native delegation-cycle restriction. The initial two catalog extractions hit that restriction; the board operator recovered their saved evidence into independent quality tasks without another extraction or Brave request. The original failed-run history is retained. Source-only quality checks use the operations lock, so they can run while the single model extraction slot is busy. One initial contact refresh was correctly held because provider/location identity did not match sufficiently; no correction was sent. Discovery search NAR-55 completed and produced NAR-58/NAR-59/NAR-60 for Tam Tam Brooklyn, Brooklyn Music Factory pricing and Brooklyn Music School.


## Evidence, branches, formats, dashboard and Padel Africa — v4

Delivered 28 October 2026. Active policy `classscout-auto-v4` retains the existing shared-catalog/client-filter separation, ownership, source, duplicate, media, daily reservation and uncertain-write protections. The shared daily write-attempt ceiling remains 20; Brave spacing, limits and reserve are unchanged. No application repository, product filter, Vercel deployment or model ranking was modified.

### 1. Automatic missing-evidence recovery

Quality reviews with missing name/address evidence can follow up to four official same-host pages, preferring contact/location/about links and the provider homepage. A recovered name must be literal, provider-specific and supported by the official title/domain; an address must be a unique literal street or the exact known branch. Multiple addresses are held. Every added fact retains its own source URL/hash. Quality then re-fetches each fact's own source rather than requiring every fact to occur on the original discovery page. No source claim is inferred from a Brave snippet or query term.

An hourly native recovery coordinator runs at :20 and queues at most two independent quality rechecks; a source draft is not repeatedly queued within 24 hours. Existing source/model outputs are reused. Live recovery resolved address gaps for Soccer Friends USA, Brooklyn Music School and Brooklyn Music Factory. Tam Tam remains held: the available same-host pages did not establish a unique provider name/address; its linked third-party location service was not silently promoted to an authoritative source.

### 2. Physical branch matching and updates

The resolver compares exact house number and normalized street name, allowing conventional street abbreviations and ignoring trailing city/ZIP text. Queens hyphenated house numbers are preserved; `126 St. Felix Street` is not truncated at "St.". Known suite identifiers must occur in the address block. On multi-location pages, contacts must be nearest to the selected street, within the bounded local context. A shared brand heading can omit a locality suffix only when brand identity and the physical street still agree. Ownership and the exact current catalog baseline are rechecked before any write.

Live result: Fancy Feet's **1295 Allerton Avenue** location was matched on its official locations page, and its phone/email correction passed private/public verification (NAR-93). Soccer Shots' **4615 Center Blvd** branch matched; its contacts already agreed, so no correction was sent (NAR-94). Old NAR-67/NAR-72 blockers were preserved and closed as superseded after confirming they had never submitted packets. The prior execution histories remained intact. Another eligible automatic phone/email correction completed for Beyond Camps Williamsburg School of Music during this delivery.

Existing verified catalog identity can now route a discovered source to contact/content refresh rather than attempting to create the same provider again. Matching requires one known provider with the same official host, source-supported name and exact street; ambiguous identities are not merged. Additional source pages for an existing publication brief can resume its deterministic preparation without generating a research-to-quality delegation loop. Source-gap searches remain budgeted and never bypass the final publication gate.

### 3. Broader publication mapping

Supported explicit source shapes now include:

- Classes priced per class, month, term or semester, without dividing fees into guessed per-class prices.
- Explicit numerical month-based ages, such as 6–18 months, retained as 6 and 18 months.
- Dated Camps with one future ISO start/end range, explicit age-specific weekday/start time/duration, and a stated day/week/session fee. Camp durations may be up to 720 minutes; a date span is limited to 120 days. Expired/reversed dates, multiple conflicting price/unit pairs and ambiguous programs are held.

Structured `price.amount`, `price.unit`, source wording and source age evidence remain authoritative. The receiving ClassScout contract still requires its legacy numeric `pricePerClass` compatibility field; it retains the stated amount, while the structured unit and public copy retain the actual month/semester/week unit. No currency or unit conversion is performed. New extended-format age bounds use explicit unit endpoints and retain their source quote plus faithful unit expansion for the canonical age-grounding validator. Existing yearly per-class behavior is preserved.

The growth roster now has 420 distinct intents, including 60 explicitly labelled Camp searches. Search hints do not establish factual format. Source, completeness, media and canonical final gates still apply to every proposed listing. Three controlled fixtures—monthly infant Classes, semester-priced Classes and future dated Camps—passed ClassScout's actual adapter and strict provider schema/age-grounding validation. Controlled media fixtures were used; no fabricated listing or fixture image was submitted to production. A live public Camp/monthly-price publication is not claimed from those contract checks.

### 4. Business results dashboard

URL: **https://paperclip.haho.ai/factory**. Uses the existing password-only access gate; no additional password or browser API credential is introduced. The proxy exposes only `/factory`, `/factory/` and `/factory/metrics` to the loopback worker; its execution endpoint is not exposed. Authentication runs before dashboard routing. Metrics are read-only and not cached by the browser.

The dashboard separates source-checked drafts, evidence gaps, confirmed publications, verified updates, uncertain outcomes, task blockers and shared search allowance. Work is grouped by catalog assignment or research intent, with unclassified items explicitly labelled. A source check is not counted as publication readiness, and an evidence-intake receipt is not counted as a published Padel record. Search consumption is shown as requests; no invented monetary price is assigned to the free allowance. It includes source recovery and the latest Padel connection census.

Seven live access checks passed (unauthenticated, authenticated, tampered and expired sessions). Desktop and 390px mobile Chrome checks confirmed four metric cards, no script errors and no horizontal overflow. Signed test cookies were short-lived and removed locally after verification.

### 5. Next brand: Padel Africa

Padel Africa was selected from the validated local client registry. Its existing instance is `https://padel-africa.doneisbetter.com`, with a separate client database and canonical machine/feed contracts. The authenticated machine catalog confirmed vertical `padel-africa`, continent `Africa`, 944 eligible catalog records and a capped 500-row slice. The slice is not a complete catalog dump; the receiving engine remains responsible for canonical deduplication and publication.

Paperclip now has a daily **Check Padel Africa catalog** routine (09:10 Budapest) and an on-demand **Submit a Padel Africa source** form. Intake requires a focused official HTTPS page, literal provider/city/street evidence and a city in the vertical's own discovery scope. It uses only the existing source-evidence ingestion contract; forced publication, raw listing patches and reprocessing are unavailable in this connector. Accepted source cards remain distinct from public publication. Submission receipts persist, and uncertain submissions cannot be replayed even if the source changes.

The connector uses the existing registered management machine identity, requesting only `management:ingest.write management:catalog.read`. Its issuer/client credentials are in root-only `/etc/paperclip-padel.env`, loaded by systemd; tokens are refreshed in memory and never reach task text, the dashboard or model input. This shares the existing machine identity; a future credential rotation must account for its other legitimate consumers. The recovery bundle now includes this restricted environment. The ClassScout model profile and the existing feeder's jobs were not changed. Sportolok's Hungarian-language automation remains outside the tested English model capability and was not enabled under an English benchmark result.

Padel's authenticated read, identity/scope check and native routine completed live (NAR-78). New-source intake success, duplicate refusal, wrong scope, missing identity and lost-reply behavior were tested with controlled transports. No unnecessary Padel record was created to manufacture a live demonstration.

### Validation and recovery

196 worker tests passed locally and on the server, alongside the three canonical format contract checks, seven access checks and browser checks. The source recovery and two branch follow-ups ran through native Paperclip jobs. Tests and prototypes sent no model inference requests. Production company work retained its production marker; no synthetic load was introduced. Backups preserve the exact packet, baseline, source and receipt ledgers. The post-delivery recovery archive contains the new modules, dashboard, nine native routines, service unit and restricted connector environment. Code rollback does not reverse catalog changes; corrective writes require a fresh baseline/source check. Do not replay an uncertain write or restore an old database over newer work to roll back code.

## Company operating dashboard — 28 October 2026

The owner dashboard at https://paperclip.haho.ai/factory now focuses on delivery and capacity rather than monetary model spend. It retains the same password gate and read-only routes. Paperclip's bundled board remains available through the navigation links; its upstream financial screens are unchanged.

The page includes confirmed ClassScout publications/updates, company tasks completed in the last 24 hours, current task states, employee assignments and last outcomes, project activation scope, direct links to blocked work, latest worker runs, configured next routine slots in Budapest time, and market coverage. Source evidence states overlap and are not presented as a conversion funnel. Padel's catalog census is not a publication count. Uncertain writes remain distinct from successful delivery.

Model reporting shows recorded successful extraction calls, tokens, observed model/context, one serialized generation slot, and local model waits. These are free local models; hosting is separate. Tokens are not a complete gateway usage census, and idle employees do not imply a failure. Run completion includes held/failed outcomes in its denominator and measures execution rather than publication. Search allowance, cooldown, reset date, and shared daily write attempt capacity are shown separately. Routine times describe configured schedules, not guaranteed executions.

Metrics fetch only whitelisted board fields and aggregate factory records. Run results are inspected only for aggregate usage; source text, errors, credentials, model answers, and customer questions are not returned. Cross-company and labelled factory-test tasks are excluded. A failed refresh retains the last successful display with a visible stale-data notice. Background tabs pause automatic refresh, and refreshes cannot overlap.

Dashboard validation: 199 factory tests passed locally and on the live host. Seven live password/session access checks passed. Real Chrome checks at desktop and 390px mobile widths found no script errors or horizontal overflow. An intercepted failed refresh preserved prior values and displayed their age; a subsequent successful refresh cleared the warning. These checks used the test-purpose header and made no inference calls or search requests. Previous dashboard code is retained under the restricted server backup directory for rollback.

## Reliable publishing and portfolio expansion — v5

Enabled on 28 October 2026 at the owner's request. The model remains the ranked `auto` route with the existing tested 8K context and one shared generation slot. Automatic quality policy remains `classscout-auto-v4`; no fact requirements or write protections were relaxed.

### Recovery and actionable holds

Search delivery has a durable attempt count and next-at timestamp. Saved pages are reused without another Brave call. Delivery retries back off (5, 10, then stop after the third failed delivery), release the queue while waiting, and stop with an explicit blocked outcome after three failures. HTTP search attempts retain their separate conservative limit. A pending delivery no longer prevents an unrelated eligible search from using an available slot.

Paperclip's native delegation rule includes creator identity as well as parent links. Therefore publication/source-search requests cross stages through the durable `company_dispatch` ledger and an independent Operations routine. Search never assigns a recovered publication directly back into its own delegation chain. The coordinator checks unchanged source-task input, company/project, exact permitted assignee, and unresolved packets before creating an idempotent follow-up. Lost task-creation replies reuse the same key. Three failed coordinator deliveries stop for attention. Existing uncertain/partial writes are never resubmitted.

Publication holds carry Paperclip's required `unblockDescriptor`, naming the executing worker itself (the native API requires this) and the exact recovery action; the Operations routine coordinates follow-up independently. Unchanged missing evidence stays held without repeated approval questions. A new source-gap search is not requested when the four-source publication bound is already full. Live commissioning exposed and corrected both the creator-cycle and missing-blocker-descriptor cases; historical failed runs remain visible.

The hourly **Recover stalled company work** routine runs at :25 Budapest. It classifies source access, branch identity, program price, schedule/age, official image and uncertain-write blockers; posts a concrete action once per changed brief/category; records next checks; and checks up to two official source sets per round. Source baselines must change before an automatic continuation is requested. Recheck intervals are one day, two days and seven days, with at most three changed-evidence recovery attempts per held task. Unresolved packets and claimed/ambiguous branches keep their existing protections. Coordinated follow-ups may wait until this routine's next slot.

### Discovery and Padel Africa

ClassScout searches now emphasize official program registration, timetable, ages and tuition, and prefer program/class/pricing/schedule URL paths before generic homepages. These are discovery priorities, not claims that every result is publishable. All publication requirements still need literal current evidence.

**Discover Padel Africa sources** runs at 10:05 and 16:05 Budapest, selecting the next city from the authenticated engine's canonical discovery scope. Only one pending Padel discovery intent is added at a time. It shares the existing Brave account broker: 2,000 account requests, automation ceiling 1,800, reserve 200, maximum 48/day and proportionate 30-minute cooldown. No quota was reset or enlarged. A Padel intent waiting at least one hour receives the same priority as normal discovery, ordered by age; publishing gaps retain priority.

Fetched Padel sources must establish a literal domain/title-supported name, one street address and a configured city together on an official page. Multi-branch or uncertain identities stay held. Eligible candidates produce an independently rechecked `padel_intake` task, which retains tenant verification, bounded catalog duplicate checks, the shared daily write-attempt cap, durable receipts and no resend of uncertain outcomes. Acceptance by the engine is not counted as public publication. The catalog slice is bounded to 500 rows; final deduplication and publication belong to the receiving engine. Strict name/address matching means some legitimate clubs will require better evidence rather than automatic intake.

### Source freshness and support knowledge

**Check ClassScout content freshness** runs every six hours at :35 and checks up to three providers that have not been checked in the last 24 hours. It tracks official source hashes, including known same-host program sources from confirmed publications (four-page bound). Changed sources queue independent research → quality → existing contact/content update gates. Inaccessible and claimed records are recorded so one unavailable source does not starve the rest of the census. Expired dated camp evidence is reported separately.

The existing connector automatically writes verified contacts and supported descriptions. Program price/schedule changes are detected as changed evidence but remain held for program-specific canonical revalidation; they are never written through contact patches, guessed, or republished as duplicate providers. Expired public listings are not silently deleted by this source checker.

**Refresh ClassScout support knowledge** runs every six hours at :50. Up to three exact provider branches receive reusable address, contact and official-website answer drafts. Each answer retains its literal evidence, source URL/hash, verification time and 24-hour expiry. Failed revalidation invalidates previous answers; missing evidence remains explicit. The reply workflow can reuse an unexpired answer only for a supported exact question and matching freshly fetched source URL/hash. Unanswered support cases are counted from existing draft reports. No customer messages, bookings, refunds or account actions are enabled.

### Dashboard and operational scope

The company dashboard at https://paperclip.haho.ai/factory adds linked-history time to publication with sample count, blocker age/action/next-check, repeated waiting/held stages in 24 hours, cumulative verified publications/updates per shared search attempt, current support knowledge, freshness census and Padel intake outcomes. The search ratio is not causal attribution; repeated waiting can be legitimate cooldown work. All-time figures and 24-hour figures remain labelled. Monetary model spending is not used.

The four additions bring the configured company total to thirteen routines, including two on-demand forms. Configuration snapshots retain `reliability_enabled` and `padel_discovery_enabled`, including through reprovisioning. No new employee, paid provider, model profile, public execution route, customer-sending channel, or ClassScout client filter was introduced.

### v5 verification

218 factory tests passed locally and on the server. The live four new routines completed their first controller/check runs. NAR-80 delivered its saved sources without another Brave call; NAR-100 completed Manhattan discovery and produced further source research. The independent coordinator delivered NAR-115; its final native run successfully recorded an `evidence_hold` with the executing agent as recovery owner. Pricing remained ambiguous after four sources, so no publication was claimed. The two superseded preparation tasks were cancelled with links; failed commissioning runs remain in history. Native typed reconciliation was used only after confirming the process stopped and no publication packet/catalog action existed.

Freshness baselines were recorded for three real providers. The first support knowledge pass prepared five ready answers and reported two evidence/access gaps; no customer message was sent. Padel's first canonical city intent is Cape Town and is queued behind the existing shared broker cooldown; automatic Padel public publication is not claimed as a live result. Transport/receipt/idempotence tests remain controlled tests, while tenant/scope/catalog reads were live. Tests covered failed delivery limits, no repeat search on delivery recovery, queue fairness, changed-input cancellation, owner protection, current-source/expiry checks, strict Padel identity and separation of accepted work from confirmed publication.

The upgraded dashboard passed seven live access checks and desktop/mobile browser checks, including retained values during an intercepted failed refresh and successful refresh recovery. No inference or search request was needed for these checks. New native business tasks retain their ordinary production purpose; synthetic tests never masquerade as production inference. A restricted recovery snapshot includes code, configured routines, durable queues, consistent factory SQLite, native SQL backups and connector secrets. SQLite integrity is checked on the off-host copy; this does not constitute a new full replacement-host restore drill.

## OpenClaw alignment and recovery — v6 (28 October 2026)

Studied the local OpenClaw company/workspace instructions, source and tests before enabling these changes. Its useful operating pattern is evidence-first discovery, gap-first enrichment, oldest-attempt maintenance, editorial polishing, then independent audit. ClassScout is one application; Management is the shared engine serving Padel Africa and Sportolok. The local OpenClaw, ClassScout, Management and Sportolok implementations were read without changing their files, credentials, jobs or ledgers. Their working directories and private authority files remain their own authority, rather than being copied into Paperclip.

The live engine contract takes precedence over older scope notes: Sportolok currently declares HU, RO, RS, SK, UA, HR, SI and AT with hu-HU. New Sportolok work preserves literal source values; Hungarian generation/translation has not passed a separate language evaluation. ClassScout remains NYC-scoped. Research, quality, publication and operations retain their independent roles and the tested shared 8K model configuration.

### Publication and structured updates

The ClassScout native ingest contract explicitly supports unknown prices. A Classes listing can therefore carry `price.evidence=unknown` without inventing a free offer or per-class conversion; an unstated timetable remains absent. Camps still require future dates, timetable and a stated fee. Branch identity, activity, child ages, source and qualified image checks remain. Precise prices/schedules live in structured fields rather than being duplicated in prose. Independent v6 checks recompute this profile before any write.

The structured program updater uses the canonical provider patch endpoint, an exact existing branch and same-source program evidence. It preserves unmatched programs and age bounds; never replaces structured recurrence with a text-only parser; refuses owner-managed records and manual price/schedule verifications. Dated programs retain actual end dates rather than being silently removed. Source and catalog baselines are reread before writing, field verification provenance is retained, and both private and public facts are read back. Submitting/uncertain packets prevent replay. The shared ceiling remains 20 daily write attempts across workflows. Enabling this connector is not a claim that a real program changed during commissioning: the initial bounded scan found no eligible change.

Recovered saved drafts cross to independent QA via the company dispatch ledger, avoiding native creator-chain delegation failures and another extraction. Existing fact gaps remain visible. Three legacy drafts reached QA but still require stronger evidence. The pricing hold on the Brooklyn Music Factory brief progressed to a qualified-image hold; it was not published. The blocker classifier now distinguishes uncertain identity/source evidence from an uncertain remote write.

### Management clients and source selection

Padel and Sportolok discovery use each authenticated engine's canonical templates and localities through Paperclip's existing shared Brave broker. Quota remains 1,800 automated requests of 2,000, 200 reserve, 48/day and proportional 30-minute cooldown. OpenClaw's unrelated search subscription/key was not copied. Search output is used for discovery; publication evidence comes from independently fetched source pages.

Venue candidates require first-party ownership, literal name, street, locality and allowed country. Bounded structured organization addresses supplement visible evidence; query locality never supplies missing facts. Directories contribute links only. Multi-venue pages can stage at most three specific branch pages for independent checks, to one expansion level. Duplicate checks include physical location. Intake acceptance is separate from publication.

Maintenance rotates local source-check attempts instead of assuming that an empty engine patch updates freshness. Governed soft publication is allowed only for a freshly verified soft-incomplete REVIEW_READY card; the receiving engine reruns hard/territory/safety gates and must return an audit receipt. Flagged/quarantined/hard-blocked cards are never force-published. Public visibility is checked separately. First live Padel soft-card sources were inaccessible and remained held. Sportolok's first round verified one actual source; two other sources were recorded NOT CHECKED. Engine catalog totals represent existing engine records, not new Paperclip publications.

There are now 18 enabled native routines: the prior 13 plus a daily structured-program queue, maintenance for each engine every six hours, Sportolok discovery twice daily and daily Management oversight. Management is engine oversight, not a third customer catalog. Customer replies remain drafts at the owner's explicit instruction. No customer delivery channel was enabled.

### Off-server backup and demonstrated application recovery

The Mac LaunchAgent `ai.narimato.paperclip-backup` runs at 03:20 Europe/Budapest and checks hourly for missed/failed due work. The Mac must be awake/logged in and able to reach SSH; missed work retries when available. It fetches the server's complete restricted recovery bundle, checks SHA-256, gzip SQL integrity, required secret/config components and a consistent SQLite integrity check before acknowledging success. Seven verified local bundles and fourteen acknowledged scheduled server bundles are retained. Manual backups are outside scheduled pruning. Archives and local logs are private; the dashboard receives aggregate status only. The local backup is off-server but remains in the same operator's custody, not immutable remote storage.

A complete isolated application restore passed against `paperclip-recovery-20261028T124716Z.tar.gz`: pinned production image, fresh PostgreSQL restoration, factory SQLite, native company API/UI, factory dashboard/metrics and restored password/session gate. Restored agents/triggers were disabled before application startup; there were zero active agents and no network egress. The test restored one company, five agents, 169 issues and 34 factory tables. Temporary successful clone resources were removed. This demonstrates application recovery, not real host replacement, public DNS failover or TLS reissuance.

### v6 acceptance

245 factory checks passed locally and on the deployed host. Tests cover unknown-price ingest, independent QA, source ownership/territory, branch expansion bounds, no unsafe force publication, structured program preservation/readback, manual verification protection, no replay after lost replies and compressed native SQL validation. Controlled cases also passed the actual ClassScout adapter/schema for unknown and stated monthly pricing; no fixture was published. Seven live password/session access checks passed. The company dashboard adds structured-program, Sportolok, off-server backup and isolated restore status. No synthetic test spent inference or search allowance.

Remaining evidence holds are operational outcomes, not abandoned setup: inaccessible sources, missing literal branch identity and missing qualified images cannot safely be invented. Existing support drafts remain unsent. Current service flags, routine registration, safe acceptance details and the tested restore report are retained with recovery backups.


## Sales partner integration

The SLG connector, required configuration, supported MCP operations and separate email delivery boundary are documented in [SLG.md](SLG.md). Workspace and scoped-key confirmation are required before activation. Existing support replies remain drafts.

## Blocked-work correction — 28 October 2026

Investigated the owner's observed 19 blocked tasks against native issue state,
worker errors, packet submission state, exact catalog records and official pages.
The blockers were not a company-wide worker outage. The dated generated acceptance
report is `blocker-recovery-20261028.json`; counts below describe that commissioning
snapshot rather than a promise that the live queue never changes.

Corrected connector checks to recognize both `official` and `authoritative` image
provenance returned by ClassScout's media contract, while retaining accepted status,
source URL, uploaded image and content-hash requirements. Equivalent full/street
addresses and North American phone formatting no longer conflict; different street
numbers, suites, explicit ZIP codes and phone numbers still conflict. Saint/St and
regional Theatre/Theater spelling, plus the Brazilian Jiu Jitsu descriptor, are
normalized for an otherwise matching provider name/address. Catalog/source host
ownership and exact physical branch checks remain mandatory. No arbitrary fuzzy
name or address matching was introduced.

Saved contact packets created before additional catalog read fields were exposed
can compare every originally reviewed field, without treating newly exposed fields
as evidence the original facts changed. Reviewed-field changes and newly claimed
ownership still stop the write. This permits a legacy contact-only packet to proceed
through its existing fresh source, owner, native validation and public/private
readback checks; it cannot write program fields or replay an uncertain submission.
The stopped legacy Luna execution was reconciled only after confirming its packet
had never submitted. Older native failures remain in history.

Padel discovery filters known directory/city-guide hosts including Time Out and
PadelVS. Historical directory candidates are recorded as completed source screening
with a rejected outcome, not an accepted venue or publication. Exact source URL and
content-hash attempts are retained across discovery tasks, including backfilled
production search receipts. Stable project/source/hash idempotency prevents repeated
extraction of unchanged failed sources. An actually changed source may be considered
again. Source extraction errors are classified before words like tuition in a URL,
so a model-validation failure is not misreported as a price gap.

The dashboard retains the full blocked count and all waiting items, separating
source-evidence waits from review-required failures/receipt questions. It labels
waiting tasks explicitly instead of implying every evidence hold requires the owner.

Live acceptance: 19 blocked became 7. Brooklyn Music Factory published and passed
private/public verification (NAR-160). Arts in Mission, Luna de Papel and Team Jucao
contact updates passed both readbacks (NAR-204, NAR-123, NAR-297). City Island Theater
Group agreed with its verified source and needed no write (NAR-244). Six directory
screens completed as rejected sources; one duplicate research task was cancelled
with a link to its retained replacement. No external customer message was sent.

Remaining items at acceptance: two sources yielded no validated extraction facts;
three Padel sources do not establish a unique physical venue; two catalog/location
records conflict with or cannot be matched to their official branch. In particular,
Soccer Friends USA's catalog street is truncated relative to its official Queens
address, and Purpose Life Church requires exact campus mapping. These records are
not silently corrected by a contact-only workflow or counted as publications.

273 checks passed locally and on the deployed host. Live access and desktop/mobile
browser checks passed, including failed-refresh recovery. No synthetic inference,
extra Brave search or fixture publication was used for verification. The recovered
business writes ran through ordinary production company tasks and their existing
shared daily ceiling. A fresh verified off-server backup follows this delivery.

## Continued evidence recovery — 28 October 2026

Empty accepted model extraction now has a deterministic fallback for an exact
provider name visibly present on the same page, matched to a provider-like title
segment and domain, and at most one unique visible street. Title segments may use
`::`; a leading The or a long domain/name prefix does not lose the identity. It
never fabricates a contact, price, age, timetable or category. A title absent from
visible text, unrelated host/name, multiple names or multiple streets cannot supply
those fields. Recovered draft facts still cross independent quality and native
publication gates. Original model usage remains recorded even if its facts were
rejected; deterministic fallback is not reported as model accuracy.

Bounded venue expansion now recognizes a first-party `/clubs` index and a specific
Shopify `/pages/...padel...club...` venue page. The existing maximum three links and
one-level expansion limit remains; finding a link is not resolving its venue.
Source-scope, literal country and unique physical-branch checks still apply.

Commissioning also delivered thirteen already queued independent quality handoffs
through the existing company coordinator. No extraction/search was repeated to
perform delivery. SLG still requires the owner's intended workspace/service and a
scoped key; sales delivery remains unconfigured and support replies remain drafts.

279 controlled checks passed locally and in the deployed staging suite before the
worker restart, including absent visible identity, unrelated domain, multiple
addresses, empty-model fallback and venue-link selection. Dated live outcomes are
kept in `continued-recovery-20261028.json` after commissioning, separate from policy.

Both Bronx recovery runs subsequently completed with saved drafts; this establishes
successful extraction, not publication. Virgin Active and Africa Padel root tasks
completed branch expansion and handed off three source checks. Those checks still
lack sufficient unique venue evidence. New saved-draft quality handoffs also reached
normal publication/contact gates and exposed additional source/address holds, so a
lower blocked count is not claimed for this round. Active continuation IDs, held
children and queue size are captured in the generated acceptance report. The
historical stopped-run guard refused in-place continuation; original task history
was retained and linked to independent successor tasks instead of bypassing it.

## Autonomous coordination (system improvement, 28 October 2026)

The native **Keep company workflows moving** routine runs every five minutes,
assigned to Operations with `skip_if_active`. This is a company workflow, not an
operator heartbeat or an external model. It delivers up to ten due saved handoffs,
plans at most two recovery requests and services at most four pending recovery
requests per tick. It makes no inference call or Brave search itself. Downstream
research/quality work uses the existing shared model queue and publication gates.
The older hourly reliability round remains responsible for evidence-check cadence.

The durable `autonomous_recovery` ledger records input hashes, root lineage,
condition, idempotent creation key, successor ID, status, retry count and due time.
Only blocked source-research, source-quality, ClassScout read checks and engine
candidate evidence tasks are eligible. Publication, contact/program patches,
engine maintenance writes, search/budget jobs and sales delivery are excluded.
Any existing publication, correction, program, engine or sales packet, in any
state, prevents this successor path. A reported native blocker alone is not proof
of stopped execution: active factory runs and nonterminal native runs stop recovery.
Cross-company, test-labelled, changed-input and completed/owner-changed tasks are
excluded. The existing native execution guard is never cleared or bypassed.

Two conditions can earn a successor: a released, workflow-specific parser contract
which addresses its recorded failure, or a stopped failed execution without a
recorded evidence hold. Ordinary missing facts, blocked/robots access, manual
rejection, source ambiguity and model waits do not become transport failures.
The same parser contract earns only one retry per lineage; already-specific branch
pages do not repeat branch expansion. Recovery is capped at three successors per
lineage, with at least fifteen minutes between planned successors. Unknown or
unsafe failures remain held rather than being retried by guessing.

Creation replies must identify the correct company and project. A lost reply
retries the identical native idempotency key. An interrupted handoff reuses the
saved successor instead of creating another. Immediately before handoff the source
input/status, stopped provider and absence of packets are checked again. The source remains unchanged: native blocked-history transitions require explicit
resume authority. The ledger records the handoff and the dashboard links its
successor while retaining the original blocked history. A handoff is not a
successful publication. Three delivery failures stop for review.
Comments are informational; the ledger is the delivery authority.

The regular handoff dispatcher now isolates lookup/validation failures per request,
uses deterministic due ordering and stable native creation keys, and backs off at
one, five and fifteen minutes instead of holding all later work behind a bad item.
The hourly source checker obeys `next_at` even when its first fetch failed and
rotates least-recently-checked evidence, avoiding repeated inaccessible sources.
Ordinary source continuations still require a changed source fingerprint; they do
not rerun just because a timer fired.

The dashboard's **Automatic recovery** panel exposes pending handoffs, last
coordinator tick, review-required recovery and a stale/overdue indication after
fifteen minutes. It does not imply that an evidence hold is solved or a message
sent. Native routine registration brings the configured portfolio to nineteen
routines (including manual forms). SLG workspace/key and business decisions remain
owner inputs; customer replies and sales sending retain their existing state.

300 controlled checks passed locally before deployment and in staging. Recovery
coverage includes crash/lost-reply idempotence, interrupted handoff, active provider,
any-state packet protection, cross-company/test tasks, owner/input changes,
lineage stopping rules, parser-contract limits, poison queue items, due-time
backoff and oldest-source rotation. Live scheduled-run evidence and acceptance
are saved separately in `autonomy-acceptance-20261028.json`. Tests do not create
fixture CRM entries, send messages, consume Brave or invoke models.

Live scheduled commissioning exposed a native restriction on closing blocked history. The controller retains those originals and labels their linked successor instead; it never calls an owner-only endpoint or clears the execution guard. An already-created successor receipt survives this adjustment and is reused by the next scheduled tick.

Scheduled acceptance: the 21:45 and 21:50 Budapest ticks ran without an operator
starting the routine or clearing a business task. They delivered three previously
queued handoffs. The first tick saved one successor receipt; the second completed
the handoff with that same successor after the native-history restriction was
handled. The queue was empty at acceptance. No duplicate successor was created.
The successor still has an evidence hold; no solved venue, catalog write or new
publication is claimed by this recovery. Controlled tests prove repeat-tick and
same-contract stopping behavior, while the two real scheduled ticks demonstrate
scheduler → worker → durable queue → native task handoff and reporting.
