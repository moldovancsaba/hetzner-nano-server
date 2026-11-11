# Release notes

Everything that reached `main` of [hetzner-nano-server](https://github.com/moldovancsaba/hetzner-nano-server), newest first. The repository has no version numbers or tags, so a release is the state of `main` at the end of a day (dates are commit dates); every commit is listed under its day with a link. Each entry says what changed for operators and clients, not just which files moved. For the reasoning behind a change read [docs/HISTORY.md](docs/HISTORY.md); for the system as it stands read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Covers history up to `67a9f91`. `python3 scripts/check_changelog.py` lists any later commit that is not yet in these notes; run it before a release and add the entry in the same change set as the work it describes. A commit that changes this file carries its own notes (it cannot link its own hash), so the check does not list it; it gets its link when the marker next moves past it.

Sections used: **Added** (new capability), **Changed** (behaviour, policy or defaults), **Fixed** (a defect corrected), **Security**, **Operations** (deployment, hosts, retention), **Documentation**.

## 2026-11-11

### Added

- Perplexity as the Paperclip fallback search: when Brave's shared allowance is resting, one request an hour (24 a day, 744 a month) serves a task's first query. Off until `perplexity_enabled` is set and `/etc/paperclip-perplexity.env` holds the key. See `paperclip/factory/PERPLEXITY.md`.

### Operations

- Released to the Paperclip host on 2026-11-11 in one idle-stopped window (no running work): `perplexity.py` and `search_workflow.py` installed, `/etc/paperclip-perplexity.env` written (root, mode 600), the unit reads it, `perplexity_enabled` set, factory restarted and checked. The previous files are kept on the host in `/root/perplexity-deploy-backup-20261111`.

## 2026-11-08

### Added
- Field probabilities from the JEV workflow and metered evidence reviews are integrated ([67a9f91](https://github.com/moldovancsaba/hetzner-nano-server/commit/67a9f91)).

## 2026-11-06

Racket Land (https://racket.land) replaced Padel Africa on 2026-11-05: every racket sport, the whole world, territory `unrestricted`. **The runtime changes below were released to the Paperclip host on 2026-11-06 (09:34-09:37 UTC, verified); the delivery code of 2026-11-01 to 11-05, which had existed only as uncommitted changes, was committed in the merge of the same day and now equals the host, except `worker.py`, `workflows_setup.py` and `provision.py`, which are ahead of it.**

### Fixed
- **A transient Paperclip HTTP 500 no longer fails a factory run.** About 0.8% of runs (75 of 9,175 since 2026-10-28, 16 since 2026-11-05) failed with `HTTP 500` followed by `handoff failed: HTTP 409 Issue run ownership conflict`. Paperclip's own `workspace_finalize` insert (`workspace_operations`) failed under its handling of the factory's issue update, the update was rolled back, and the hand-off then met a run that no longer owned the issue. `Board.call` now retries a PATCH that answers 500, 502, 503 or 504 twice (after 2 s and 5 s), and never retries a create. `test_board_retry.py` pins it. Released to the Paperclip host with `paperclip/integration/ops/patch_factory_files.py` (digest-checked, idle-stopped, backed up, health-checked, restores on failure). The underlying insert failure is inside the Paperclip server and is not fixed here.

### Changed
- **The Padel Africa identity of the Paperclip factory is now Racket Land.** `padel.py` is `racket_land.py`; the workflow kinds are `racket_*`, the search purpose is `racket`, the tables are `racket_packets` and `racket_discovery_cursor`, the credentials are `RACKET_SSO_*` in `/etc/paperclip-racket.env`, the project and routine titles, `factory.json`, the dashboard and the tests follow. The protocol client id `padel-africa` is unchanged until the exchange scope is re-approved. Released to the Paperclip host at 19:33 UTC with `paperclip/integration/ops/rename_to_racket_land.py` (digest-checked files, backups, stored names migrated, rollback); see [the alignment note](paperclip/integration/RACKET-LAND-ALIGNMENT.md#rename-release-2026-11-06-1933-utc).
- **Racket Land source qualification ([3c42953](https://github.com/moldovancsaba/hetzner-nano-server/commit/3c42953)).** The factory validates the authenticated vertical `racket-land` with `territoryScope: unrestricted`, requires a sport word that the application declares (instead of the word "padel"), sends engine and evidence-intake requests to `https://racket.land`, and accepts a country that is in the bundled registry (`racket_countries.json`, 249 ISO codes, 291 names). `ops/deploy_factory.py --racket-land-runtime` with `ops/racket_runtime_patches.json` patches the host files.
- **Plain official pages resolve in any country ([01dee2e](https://github.com/moldovancsaba/hetzner-nano-server/commit/01dee2e)).** A page without structured data used to resolve only for nine African and eight European countries and only when exactly one declared discovery locality was written on it. For the worldwide scope the country now comes from the full registry (longest name wins; names such as Georgia or Jordan count only as the last part of a line) and the city from the address line of the one street. A city that cannot be read still needs exactly one declared locality, otherwise the page stays held. The continent and countries scopes, and so the legacy `padel-africa` slug and Sportolok, behave as before. "USA", "UK" and "UAE" are not in the registry; a page that uses only those stays held.
- **More racket directories are refused ([01dee2e](https://github.com/moldovancsaba/hetzner-nano-server/commit/01dee2e)).** `matchi.se`, `playbypoint.com`, `courtreserve.com`, `clubspark.lta.org.uk`, `tennis.com`, `squashlevels.com` and `pickleheads.com` cannot establish a venue identity. They match as a domain or subdomain, not as a substring.
- **Link patterns follow the vertical ([01dee2e](https://github.com/moldovancsaba/hetzner-nano-server/commit/01dee2e)).** For `racket-land` the host, venue-page and branch-page patterns use the vertical's sport words, generic venue words and declared localities instead of `padel|club|sport` and the Cape Town, Johannesburg and City Rock names. Other verticals keep the fixed patterns. `branch_links` takes the vertical as an optional third argument.
- **Racket Land wording ([01dee2e](https://github.com/moldovancsaba/hetzner-nano-server/commit/01dee2e), [8756562](https://github.com/moldovancsaba/hetzner-nano-server/commit/8756562)).** Task comments and errors from `padel.py`, both company dashboards, the intake form's city label and the provisioning text say Racket Land and "worldwide scope verified". The Paperclip project name "Padel Africa", the routine titles, the `padel_*` workflow names, the `PADEL_SSO_*` variables and the `padel_packets` table are unchanged because the host matches or stores them by name.

### Operations
- Released: `engine_ops.py`, `padel.py` and `venue_identity.py` (09:34 UTC), `dashboard.html` (09:35, guarded file swap, backup `dashboard-20261106T093539Z.html`) and `brave.py` (09:37, the `padel` kind searches as country `ALL`, English; `ALL/en` added to the reviewed pairs; the release mode `--racket-land-runtime` now also covers `brave.py`). The manifest rows were first built against the parent of 3c42953, but the host already ran 3c42953, so they were rebuilt from it; a dry run reproduced the branch files before anything was applied. The `brave.py` edit is committed as well (sha256 `ddb7f5a6…`, equal to the host copy), together with the delivery code of 2026-11-01 to 11-05; `worker.py` in the repository is ahead of the host (idempotent issue creation, a ClassScout street filter, the GDS company routes) and is not deployed. Not released: `workflows_setup.py`, `provision.py`, the React dashboard. Remaining steps in [docs/OPERATIONS.md](docs/OPERATIONS.md#racket-land-deployed-2026-11-06).

### Documentation
- Added the status, plain-page, directory and Brave-locale sections to the Racket Land alignment note; updated the factory README, WORKFLOWS (dated notes, the historical text is kept), BRAVE, the Paperclip README (known limitation) and ARCHITECTURE.
- **Brave storage policy.** The retention text in `paperclip/factory/BRAVE.md` and `brave-plan.json` now says that storing Brave results is permitted under fair usage, as Brave told the owner in writing (reported 2026-11-06), while the existing budgets hold. The code is unchanged: it still keeps results in RAM and stores no new data, and a persistent result store is not built yet.

### Also on 2026-11-06
- **References for entries above:** the Paperclip identity rename to Racket Land ([b3359d3](https://github.com/moldovancsaba/hetzner-nano-server/commit/b3359d3)), the retry of a transient 5xx on a Paperclip issue update ([cc6efc2](https://github.com/moldovancsaba/hetzner-nano-server/commit/cc6efc2)), the merge of the worldwide rules branch as released to the host ([94a3b8e](https://github.com/moldovancsaba/hetzner-nano-server/commit/94a3b8e)), the repository-only record of the worldwide rules and the Brave locale change ([988937d](https://github.com/moldovancsaba/hetzner-nano-server/commit/988937d)), the record that the runtime, dashboard page and country-neutral Brave locale are deployed ([3bcba4d](https://github.com/moldovancsaba/hetzner-nano-server/commit/3bcba4d)), the documentation and evidence records of the 2026-11-01 delivery ([e2049d7](https://github.com/moldovancsaba/hetzner-nano-server/commit/e2049d7)), and the Brave storage policy text ([4bdc748](https://github.com/moldovancsaba/hetzner-nano-server/commit/4bdc748)).
- **Backups and restore:** seven daily recovery points are kept and duplicated SQL history is excluded ([a42ce81](https://github.com/moldovancsaba/hetzner-nano-server/commit/a42ce81)); the daily backup calendar points are capped and pending captures preserved ([c703874](https://github.com/moldovancsaba/hetzner-nano-server/commit/c703874)); restore resources are provisioned for the current database size ([278dc59](https://github.com/moldovancsaba/hetzner-nano-server/commit/278dc59)); the completed cleanup and the verified full-stack recovery are recorded ([ff17d0c](https://github.com/moldovancsaba/hetzner-nano-server/commit/ff17d0c)).
- **Racket runtime release:** the release patch rows are built from the deployed source ([2e24dff](https://github.com/moldovancsaba/hetzner-nano-server/commit/2e24dff)); the release can patch `brave.py` so Racket Land searches carry no country bias ([7340c28](https://github.com/moldovancsaba/hetzner-nano-server/commit/7340c28)); the `padel` kind is searched without a country bias, as on the host ([365101e](https://github.com/moldovancsaba/hetzner-nano-server/commit/365101e)); the dated Racket Land notes in WORKFLOWS and the Brave routine note are updated to the deployed locale ([fdd428c](https://github.com/moldovancsaba/hetzner-nano-server/commit/fdd428c), [b0de1e6](https://github.com/moldovancsaba/hetzner-nano-server/commit/b0de1e6)).
- **Repository caught up with the host:** the delivery code of 2026-11-01 to 11-05 is committed exactly as it runs on the host ([c5f1ab1](https://github.com/moldovancsaba/hetzner-nano-server/commit/c5f1ab1)); `brave.py` is committed with the `web-locale-v2` contract as it ran before the Racket Land locale release ([aa7f400](https://github.com/moldovancsaba/hetzner-nano-server/commit/aa7f400)); `worker.py` is ahead of the host with idempotent issue creation and the ClassScout street filter and is not deployed ([7afc21e](https://github.com/moldovancsaba/hetzner-nano-server/commit/7afc21e)).

## 2026-11-02 to 2026-11-05: Paperclip source exchange

Work on the scoped exchange between the Paperclip factory and OpenClaw; the design, commissioning steps and acceptance records are in `paperclip/integration/`. One line per commit, as the commit subject states it.

### Added
- 2026-11-02: the durable scoped Paperclip source exchange ([fb7fa56](https://github.com/moldovancsaba/hetzner-nano-server/commit/fb7fa56)), guarded factory exchange hooks with accessible combined results ([a91dbe0](https://github.com/moldovancsaba/hetzner-nano-server/commit/a91dbe0)), fair source allocation with causal GDS company delivery views ([9660c65](https://github.com/moldovancsaba/hetzner-nano-server/commit/9660c65)), and a distinction between verified operations with deduplicated candidate qualification ([cf334b5](https://github.com/moldovancsaba/hetzner-nano-server/commit/cf334b5)).
- 2026-11-05: a reviewed source-only project runtime through the shared search lane ([6aa029d](https://github.com/moldovancsaba/hetzner-nano-server/commit/6aa029d)), recorded healthy and default-off ([bd3309c](https://github.com/moldovancsaba/hetzner-nano-server/commit/bd3309c)); native Management and SLG mutations are fenced during a reviewed writer handoff ([eae0d9e](https://github.com/moldovancsaba/hetzner-nano-server/commit/eae0d9e)), recorded healthy ([5fed020](https://github.com/moldovancsaba/hetzner-nano-server/commit/5fed020)); native source delivery credentials are isolated by client scope ([b322053](https://github.com/moldovancsaba/hetzner-nano-server/commit/b322053)), recorded verified ([22d428d](https://github.com/moldovancsaba/hetzner-nano-server/commit/22d428d)); literal provider identity and locality are retained in source exchange offers ([aa671d4](https://github.com/moldovancsaba/hetzner-nano-server/commit/aa671d4)), recorded verified ([2504ceb](https://github.com/moldovancsaba/hetzner-nano-server/commit/2504ceb)).
- 2026-11-04: protected systemd credentials are supported in the native source transport ([fc063ba](https://github.com/moldovancsaba/hetzner-nano-server/commit/fc063ba)); project-scoped native catalog writer handoff controls are prepared ([9da1dc6](https://github.com/moldovancsaba/hetzner-nano-server/commit/9da1dc6)).
- 2026-11-03: RC5 description gaps are published for existing-record source enrichment ([6993392](https://github.com/moldovancsaba/hetzner-nano-server/commit/6993392)).
- 2026-11-02: public evidence is bounded and independently verified native pages are handed off ([dc0c260](https://github.com/moldovancsaba/hetzner-nano-server/commit/dc0c260)); scoped feedback is batched within the existing coordinator budget ([f4925b3](https://github.com/moldovancsaba/hetzner-nano-server/commit/f4925b3)); the canonical exchange delivery plan is published with implementation status ([e7fdc77](https://github.com/moldovancsaba/hetzner-nano-server/commit/e7fdc77)); combined results browser checks require zero WCAG findings ([82a1aec](https://github.com/moldovancsaba/hetzner-nano-server/commit/82a1aec)).

### Changed
- 2026-11-05: additional client projects require an explicit source-policy review ([2f52c42](https://github.com/moldovancsaba/hetzner-nano-server/commit/2f52c42)); native release stop control uses verified process pausing ([59cfd9f](https://github.com/moldovancsaba/hetzner-nano-server/commit/59cfd9f)).
- 2026-11-04: ClassScout source capacity is reserved for complete identity evidence ([510b6b1](https://github.com/moldovancsaba/hetzner-nano-server/commit/510b6b1)).
- 2026-11-02: shadow feedback is kept distinct from measured catalogue yield ([201ebc7](https://github.com/moldovancsaba/hetzner-nano-server/commit/201ebc7)); publication is projected from the latest exact listing readback ([d768bfd](https://github.com/moldovancsaba/hetzner-nano-server/commit/d768bfd)).

### Fixed
- 2026-11-04: non-regular exchange credentials are refused before opening ([7f8ff89](https://github.com/moldovancsaba/hetzner-nano-server/commit/7f8ff89)).
- 2026-11-02: exchange recovery and stale source observations are fenced in RC3 ([75f707b](https://github.com/moldovancsaba/hetzner-nano-server/commit/75f707b)); replacement-inbox receipts are recovered and native hooks deployed only while idle ([3ee7607](https://github.com/moldovancsaba/hetzner-nano-server/commit/3ee7607)); the repair allowance is enforced per field across changing gap combinations ([5ac6939](https://github.com/moldovancsaba/hetzner-nano-server/commit/5ac6939)).

### Operations
- 2026-11-02: protected metadata dashboard commissioning ([4cd3a8b](https://github.com/moldovancsaba/hetzner-nano-server/commit/4cd3a8b)), the latest verified metadata service revision ([1b0ae82](https://github.com/moldovancsaba/hetzner-nano-server/commit/1b0ae82)), the RC3 metadata deployment with business admission off ([ab45f8b](https://github.com/moldovancsaba/hetzner-nano-server/commit/ab45f8b)), and the disabled native hook deployment with hard-crash recovery evidence ([c28a20f](https://github.com/moldovancsaba/hetzner-nano-server/commit/c28a20f)) are recorded.

## 2026-11-01: benchmarks

### Added
- InternVL image suites and Marqo screening are completed and the verified ranked defaults published ([a5670a7](https://github.com/moldovancsaba/hetzner-nano-server/commit/a5670a7)); benchmark resume inventory is fixed so incomplete InternVL suites continue ([0b00362](https://github.com/moldovancsaba/hetzner-nano-server/commit/0b00362)); Hungarian round 4 measured Phi-4 Mini and rejected it ([0a9c9be](https://github.com/moldovancsaba/hetzner-nano-server/commit/0a9c9be)).

## 2026-11-01 — Proposed OpenClaw integration

### Documentation
- Prepare a source-exchange workflow, scoped API contract, synthetic examples and required failure scenarios for Paperclip and OpenClaw. The plan includes transactional intake, independent evidence checks, destination write coordination, shared search accounting and a limited NYC pilot. No endpoint or runtime behavior is enabled. [Plan](paperclip/INTEGRATION-PLAN-20261101.md).
- Extend the delivery scope through production service installation, scoped credential provisioning, activation on both systems, live bidirectional acceptance, recovery verification and operational handover. Distinguish deployment, verified live exchange and evaluated pilot outcomes; no activation was performed by this planning update.

## 2026-11-01 — Paperclip automatic delivery maintenance

- Fix Sportolok web-search country/language parameters, validate requests before dispatch, redact 422 diagnostics and queue one-time corrected-contract successors under the shared Brave budget.
- Freshly prepare expired automatic publication/contact packets with bounded durable scheduled renewal, preserving human declines, native execution history and every submitted/uncertain write. Recovery hydrates bounded native details when issue-list summaries omit a stopped execution.
- Follow focused official pages for editorial evidence, bound and deduplicate independent research, isolate publication queue holds, and expose evidence categories. Disable native broad title dedup for keyed factory tasks, verify exact handoff receipts and automatically repair a recorded wrong-provider research handoff with retained audit history.
- Expand structured-program selection to known programs and publications; preserve active tasks, report skips, prefer program provenance and check runtime flags. Run bounded scans twice hourly.
- Validation: 453 local and isolated server checks passed for this release. Live scheduled acceptance is recorded separately in `paperclip/delivery-acceptance-20261101.json`.

## 2026-10-31

### Added
- **Hungarian round 4: Phi-4 Mini measured and rejected.** The one plausible small candidate not yet tested (Q3_K_M, 2.12 GB) got the same 35 frozen cases at the served ctx1024/batch8 profile. It answered the first two structured cases incorrectly and its runner was killed for memory at the 2800 MiB cap on the third, so the run stopped after 3 of 35 cases; the served Qwen3-4B profile and every default are unchanged. The attempt is in the tested-model index (so the daily discovery will not repeat it unchanged) and on the public dashboard. The host was restored afterwards. [Report](benchmarks/non-english/hu-round4/REPORT.md).

### Fixed
Eighteen of the 22 defects found by the documentation review are fixed in the repository, each with a unit test; the status of every one is in [docs/GAP-ANALYSIS-2026-10-30.md](docs/GAP-ANALYSIS-2026-10-30.md#defects-found-while-checking). **All of them were deployed to both hosts on 2026-10-31** (what was copied, what was checked and what was not: [docs/OPERATIONS.md](docs/OPERATIONS.md#deployed-on-2026-10-31)).
- **Gateway queue report.** `GET /v1/queue` reports the calling tenant's own `per_service_limit` (1 for Paperclip, not always 4) and a new `active_timeout_seconds` for the running job. The host monitor flags a job as stuck after that timeout plus 120 s (at least 300 s), so a valid 900 s job on the 8K profile no longer raises a critical alert.
- **Metrics cap.** The monitor's and external watchdog's 30-second `GET /v1/queue` polls (test-marked, answered 200 or 401) are no longer stored, so they stop using about 172,800 of the 200,000 events kept over 30 days.
- **Cleaner reports.** The hourly cleaner deletes `cleanup-*.json` reports older than `keep_cleanup_report_days` (30), except `latest.json` and any report that removed a model.
- **Chat body limit.** The chat server's check is 128,000 bytes, the same as Caddy's, instead of an unreachable 256 KiB.
- **Discovery collector.** Redirect targets are checked against the host allowlist and must be HTTPS; the tested-model index lists the three models whose ranked tasks were missing.
- **`provision.py` keeps the metered Segmind lane.** A re-run keeps every setting it does not derive from the live company (`remote_llm`, switches, limits) and writes 3 as the first-install candidate limit instead of 2.
- **Recovery bundle and restore drill.** The bundle includes the Segmind env file. The restore drill now measures its network, production-file and image assertions and fails if one is false; before, three of them were written as constants.
- **SLG setup.** `configure-slg.py` leaves existing schedule triggers as they are instead of re-enabling every one.
- **Discovery backlog.** `research_backlog` counts every active task; before, it read one page of 500.
- **Dashboard billing line.** It names the metered Segmind lane and shows the last 24 hours' calls and cost from the ledger once the lane is on; before, it always read "Free local models".

### Changed
- **Candidates are worked oldest-touched first.** Every candidate now has a last-touched time (`candidate_touches`), and the publication queue and the evidence recheck queue always take the candidates touched longest ago, stamping them as they are selected. A blocked, failing or skipped candidate moves behind all the others instead of holding a slot; the queue visits every ready draft before it repeats any. Before, the publication queue paged through newest-first with an offset that moved as drafts changed, and yesterday 88 of its 231 checks (at least) were repeats. Tests: `test_candidates.py`. Deployed to the Paperclip host on 2026-10-31; the 08:45 UTC queue round was the first to use it.
- **The gate switch stops every automatic write.** `automatic_quality_gate.enabled` used to stop only new-listing publication and contact/content refresh; program updates, engine intake and publish, and Padel intake ignored it and only took a slot from the daily cap. Their reservation now refuses while the switch is not true, the run is held ("Automatic quality hold: automatic writes are switched off") and no write is sent. The switch is on today, so normal running is unchanged. Tests: `test_gate_switch.py`. Deployed to the Paperclip host on 2026-10-31 at 09:09 UTC; the switch is on, so normal running is unchanged.
- **The older Padel implementation is removed.** `padel_discovery`, `padel_candidate` and `queue_padel_candidate` in `company_ops.py` ran only when the engine client flag was off and had never written a packet. Padel kinds now go to the engine client only and fail with a clear message when it is not configured. Deployed at 09:09 UTC; the first engine-routed routine on the new routing had not run yet at that point.
- `scripts/deploy_gateway_update.py` is retired (it left out four modules the gateway imports; it now refuses to run without an explicit flag); `scripts/verify_gateway.py` takes job types and defaults from `config/job-routes.json` and `config/model-policy.json`; `tests/test_gateway.py` reads the text default from the policy.
- Removed eight `factory.json` keys that no code reads, and three unused single-format parsers from `publishing.py`; the publication tests now call the parsers production uses.

### Documentation
- Documentation and comment review of 2026-10-30 ([b8be171](https://github.com/moldovancsaba/hetzner-nano-server/commit/b8be171)); the findings are in [docs/GAP-ANALYSIS-2026-10-30.md](docs/GAP-ANALYSIS-2026-10-30.md). Three of the 22 defects wait for an owner decision (an expired automatic packet, the gate switch on engine and program writes, the second Padel path) and one is by design (one identity for both engines).
- Added the system architecture ([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)), a benchmark and ranking index ([docs/BENCHMARKS.md](docs/BENCHMARKS.md)), code conventions ([docs/CODE-CONVENTIONS.md](docs/CODE-CONVENTIONS.md)), a dated gap analysis ([docs/GAP-ANALYSIS-2026-10-30.md](docs/GAP-ANALYSIS-2026-10-30.md)) and these release notes.
- Rewrote the README as an entry point with a documentation map and repository map; the dated round-by-round paragraphs moved to the benchmark index.
- Corrected statements that no longer matched the code across the operating, access, job-router, model-policy, retention, backlog and Paperclip documents, and added a Known limitations section to the operations and Paperclip pages.
- Added module docstrings to every Python file that lacked one, fixed misleading comments, and documented the non-obvious invariants (storage lease epoch, circuit breaker, request-header trust, error-text routing, write reservation order). No executable code changed.
- Added `scripts/check_changelog.py`.

### Commit references
- 18 of the 22 defects found by the documentation review are fixed ([1863be3](https://github.com/moldovancsaba/hetzner-nano-server/commit/1863be3)); candidates are worked oldest-touched first so none can hold a queue slot in a loop ([8735529](https://github.com/moldovancsaba/hetzner-nano-server/commit/8735529)); the deployment of the defect fixes and the candidate order is recorded ([b8f8dbc](https://github.com/moldovancsaba/hetzner-nano-server/commit/b8f8dbc)); the gate switch stops every automatic write and the older Padel path is removed ([b9cac4b](https://github.com/moldovancsaba/hetzner-nano-server/commit/b9cac4b)); the 09:09 UTC deployment of the gate-switch and Padel changes is recorded ([6c1e6fb](https://github.com/moldovancsaba/hetzner-nano-server/commit/6c1e6fb)).

## 2026-10-30

### Added
- **Category banner when no official image qualifies** ([3a814b0](https://github.com/moldovancsaba/hetzner-nano-server/commit/3a814b0), [d2a9f33](https://github.com/moldovancsaba/hetzner-nano-server/commit/d2a9f33)). The publication workflow no longer stops on a missing image. It asks ClassScout for its own hosted category banner (ClassScout 0.201.188) and accepts only that banner, marked as a placeholder in the packet proof; any other image must still come from the official page. Verified live before release; deployed 15:56 UTC.
- **Reasons for editorial-brief gaps, and a model choice at that step** ([843ea0e](https://github.com/moldovancsaba/hetzner-nano-server/commit/843ea0e)). The brief step now names the first failed field (name, address, borough, activity, format or neighborhood) with the candidates found, stores the full list and shows it in the queue report. The metered Segmind model may choose between borough, neighborhood and activity values that the pages already name; a choice counts only when its quote is on the pages and, for a place, next to the street address. First run over 87 discovery drafts: 24 asked, 5 accepted, complete briefs 12 to 17, $0.064.

### Changed
- **Phones compare by digits; more age phrasings are read** ([410e2b1](https://github.com/moldovancsaba/hetzner-nano-server/commit/410e2b1)). A leading country code no longer makes a correct phone number fail the contact check. The age parser now reads "ages three to ten", "aged 4 to 11", "ages 3 through 6" and halves such as 2.5-3.5 (kept exact in months); open ranges, grades and "toddlers" are still refused.
- **Model retention window is three days** ([43e2bc7](https://github.com/moldovancsaba/hetzner-nano-server/commit/43e2bc7)). Models ranked below third and unused for three days are removed; the window and the one-time history grace are values in `config/model-storage-policy.json`. The first run under the rule removed ten models and took the inference host's disk from 85% to 51%.

### Fixed
- **The public comparison tolerates ClassScout's em-dash rewrite** ([88dab5a](https://github.com/moldovancsaba/hetzner-nano-server/commit/88dab5a)). ClassScout serves "A, B" for a stored "A — B", so a listing with a dash could never verify; the public comparison now mirrors that rule while the private record is still compared exactly. The recovery and autonomy planners also page through all issues.
- **Guards against wrong briefs** ([410e2b1](https://github.com/moldovancsaba/hetzner-nano-server/commit/410e2b1)). A brief whose borough contradicts the verified address, a name containing `|`, and pages from third-party lists or directories are now held instead of becoming listings.
- **The dashboard and daily digest saw a third of the tasks** ([16b0077](https://github.com/moldovancsaba/hetzner-nano-server/commit/16b0077)). Paperclip answers 500 issues per call by default; `issue_pages.py` now pages through the whole list, so the funnel matches the database.

### Security
- **SSH is key-only with fail2ban on both hosts** ([16b0077](https://github.com/moldovancsaba/hetzner-nano-server/commit/16b0077)): password login off, three tries, `sshd` jail; applied with an automatic revert and proved with a fresh key login and a refused password login. Configuration and notes are in the repository.

## 2026-10-29

### Added
- **Metered Segmind model lane** ([26a1512](https://github.com/moldovancsaba/hetzner-nano-server/commit/26a1512), [a5085a4](https://github.com/moldovancsaba/hetzner-nano-server/commit/a5085a4)). The Research Analyst can ask a Segmind-hosted model to fill missing facts from the same public page; every value still needs a verbatim quote, only the research role can reach it, and a durable ledger caps calls and cost. Deployed switched off, then enabled with a $10 monthly cap ($0.40 a day, 3,000 calls a month, 150 a day). The trigger also covers a missing name or address. Pilot on stuck drafts: 23 re-researched, 20 now ready for review, 24 calls, $0.0687.
- **Segmind spend panel and a 120% overspend guard** ([c5ef13d](https://github.com/moldovancsaba/hetzner-nano-server/commit/c5ef13d)). The company dashboard shows month and day spend against the caps, the account balance and the last five weeks; before a call, at most hourly, the lane reads the real balance and cools down until the next month past 120% of the cap.
- **Paperclip host and research factory tracked in Git** ([6cbe3c0](https://github.com/moldovancsaba/hetzner-nano-server/commit/6cbe3c0)). The deployment, access gate, backup and restore scripts, factory workflows, engines, documentation and 300 unit tests were deployed but had never been committed. Research files that quote real third-party contact details stay local and ignored.

### Changed
- **Round 6 closed with no ranking change** ([ad0b20c](https://github.com/moldovancsaba/hetzner-nano-server/commit/ad0b20c), [1b91d4e](https://github.com/moldovancsaba/hetzner-nano-server/commit/1b91d4e)). LFM2 1.2B, OLMo 2 1B, SmolVLM2 256M and InternVL3.5 1B ran full suites; Granite 4 1B Hybrid, MiniCPM-V 4.6 Q5_K_M and Qwen3.5 0.8B stay the defaults. InternVL3.5 1B is recorded as incomplete (a runner fault after 9 of 32 cases), not as a quality failure. Policy `2fa66c02` and the refreshed dashboard (52 variants in 22 cohorts) were deployed and verified 11 of 11 through the public API.
- **The deployed 8K text-context state is in Git** ([47232f4](https://github.com/moldovancsaba/hetzner-nano-server/commit/47232f4)). Production had served the token-budgeted 8192-token Granite profile since 2026-10-27 without it being committed; the gateway, chat service, compose settings, systemd units, deploy helpers, tests and evidence now match the server.

### Fixed
- **Documentation drift after the gateway migration** ([a269280](https://github.com/moldovancsaba/hetzner-nano-server/commit/a269280)). Caddy holds no bearer keys and does not authenticate; the gateway does. The five tenants and the real per-tenant limits are described, and the retired moderation worker is marked rollback-only.

### Operations
- **Both hosts patched and rebooted once** ([3373017](https://github.com/moldovancsaba/hetzner-nano-server/commit/3373017)), one at a time with the queue idle; downtime under a minute each. Docker Engine packages are held back for a planned upgrade.

## 2026-10-28

### Added
- **Broader Camera evaluation and ranked defaults** ([d728f05](https://github.com/moldovancsaba/hetzner-nano-server/commit/d728f05), [c1d6d1f](https://github.com/moldovancsaba/hetzner-nano-server/commit/c1d6d1f), [bb99779](https://github.com/moldovancsaba/hetzner-nano-server/commit/bb99779), [6a09ca6](https://github.com/moldovancsaba/hetzner-nano-server/commit/6a09ca6), [9db70ff](https://github.com/moldovancsaba/hetzner-nano-server/commit/9db70ff)). Recognition on 32 public photographs with paired robustness variants and counting probes, and moderation on 41 cases in nine categories, with frozen references and separate scoring. MiniCPM-V 4.6 1B became the recognition default and Qwen3.5 0.8B the moderation default; all 38 final API checks passed.
- **Usage reporting and watchdogs** ([8408250](https://github.com/moldovancsaba/hetzner-nano-server/commit/8408250)). Per-tenant, per-purpose counts, outcomes and timings with no content columns; debounced in-chat alerts for failures and recovery; an independent reachability check from the second host. Email is disabled by the owner.
- **Public benchmark dashboard** ([6607659](https://github.com/moldovancsaba/hetzner-nano-server/commit/6607659)). A shareable page with historical rankings, every attempted variant including failures, and source evidence; no login.
- **Experimental Hungarian route** ([55dcb79](https://github.com/moldovancsaba/hetzner-nano-server/commit/55dcb79)). `text_chat_hu` with its own ranking and quality gate; the best measured profile is available for explicit testing and did not pass the gate.
- **Round 4 and Round 5 results** ([a1ed3f4](https://github.com/moldovancsaba/hetzner-nano-server/commit/a1ed3f4), [6ed18e3](https://github.com/moldovancsaba/hetzner-nano-server/commit/6ed18e3)). Ten new text and image candidates, then three further variants; MiniCPM-V 4.6 Q5_K_M took the recognition lead and was deployed.
- **Moderation specialists and Hungarian follow-up** ([38a982a](https://github.com/moldovancsaba/hetzner-nano-server/commit/38a982a)). Two NSFW classifiers evaluated on the 41 frozen images, Camera's twelve rejection reasons mapped to what the API can signal, and further Hungarian candidates tested.

### Changed
- **Retention keeps the top three models per task** ([3e10977](https://github.com/moldovancsaba/hetzner-nano-server/commit/3e10977)), with recent-use safeguards, replacing the earlier top five.

### Fixed
- **Recent out-of-memory events are told apart from historical Docker flags** ([6e77a65](https://github.com/moldovancsaba/hetzner-nano-server/commit/6e77a65)), so the monitor reports a recent kill separately from a flag Docker kept from an earlier one.
- **The served Hungarian low-memory profile is described correctly** ([ae592b8](https://github.com/moldovancsaba/hetzner-nano-server/commit/ae592b8)).

## 2026-10-27

### Added
- **Initial repository** ([1f02229](https://github.com/moldovancsaba/hetzner-nano-server/commit/1f02229)). Setup and operations documentation, access notes, and the first measurements: the seven-model capability comparison, Round 2 (separate image and text results) and Round 3 (five more text and six more image variants).
- **Camera review-assistance moderation** ([4702c19](https://github.com/moldovancsaba/hetzner-nano-server/commit/4702c19), [2fbd267](https://github.com/moldovancsaba/hetzner-nano-server/commit/2fbd267)). The independent nine-category benchmark and its limits, then authenticated `/v1/moderation/*` jobs: bounded in-memory results, input validation and resizing, explicit review-only output, nullable categories and idempotency, with a separate 6 MB proxy limit.
- **One authenticated model queue** ([9173798](https://github.com/moldovancsaba/hetzner-nano-server/commit/9173798)). A FIFO gateway routes `text_chat`, `image_moderation` and `image_recognition` jobs, with per-tenant keys and permissions, queue bounds, result expiry, idempotency and an upstream-uncertain circuit. Cutover used a maintenance window, backups and a drained model; mixed HTTPS testing and twelve unit tests passed.
- **Ranking-driven defaults** ([19b1088](https://github.com/moldovancsaba/hetzner-nano-server/commit/19b1088)). A generated policy turns separate ranking evidence into task defaults with exact tested digests; the gateway hot-loads it and exposes installed, tested alternatives; unknown or changed artifacts are blocked, never pulled or substituted.
- **Continuous discovery and retention rules** ([0e4080e](https://github.com/moldovancsaha/hetzner-nano-server/commit/0e4080e)). A daily metadata-only collector (03:30 Budapest), the research backlog, retention and training boundaries, five-minute result expiry with client acknowledgement, and removal of two declined models with evidence kept.
- **Automatic model retention** ([220b384](https://github.com/moldovancsaha/hetzner-nano-server/commit/220b384)). An hourly cleaner under a gateway maintenance lease keeps ranked and recently requested weights, with content-free usage tracking and test-request markers.

### Fixed
- **Text routing corrected to Granite** ([8ee1410](https://github.com/moldovancsaha/hetzner-nano-server/commit/8ee1410)). The new queue had preserved the earlier Qwen3 route even though Granite 4 1B Hybrid led the English benchmark; text jobs now use it and chat shows the model that actually answered.

### Documentation
- A whitespace normalisation in a service verification snapshot ([643458e](https://github.com/moldovancsaba/hetzner-nano-server/commit/643458e)).

## Before 2026-10-27

The inference host was set up on 2026-10-26: server and key creation, Docker and Ollama with a pinned image, Caddy with HTTPS, firewall, DNS, project keys and the first Qwen3 1.7B baseline. The record is in [docs/HISTORY.md](docs/HISTORY.md); the repository's first commit is the 2026-10-27 import above.

## Source exchange implementation

- Added the scoped loopback broker, exact-byte operation receipts, fenced leases, bounded aggregate snapshots, factory outbox/projection helpers and offline recovery tools. Source admission and claims default to disabled; production commissioning and client activation have separate evidence gates. See [the exchange guide](paperclip/integration/README.md).

## Source exchange adapters and combined results

Added opt-in factory evidence/outbox and causal feedback hooks, a GDS-only results view, bounded streamed snapshot validation and a metadata-only gated deployment path. Admission and claims remain disabled; no business worker restart or new notification cadence. The staged factory snapshot passes 420 tests, broker passes 16, dashboard browser checks pass 3.

### Readback attribution refinement

Combined views report verified operations without claiming every operation changed a record. Missing processing coverage stays unmeasured. Qualification aggregates shared branch candidates once across source packet lineages.

### Causal delivery history and GDS company shell

Added durable fair source allocation with one-fifth exploration, typed bounded causal snapshots and a GDS replacement for the company overview. Missing predecessor events cannot inflate outcome totals; matching readback requires fields and revision evidence. Browser checks cover disclosures, retained refresh focus and zero WCAG findings. Admission, claims and business imports remain off; no new schedule or paid call.
