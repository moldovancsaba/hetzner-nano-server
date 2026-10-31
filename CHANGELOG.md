# Release notes

Everything that reached `main` of [hetzner-nano-server](https://github.com/moldovancsaba/hetzner-nano-server), newest first. The repository has no version numbers or tags, so a release is the state of `main` at the end of a day (dates are commit dates); every commit is listed under its day with a link. Each entry says what changed for operators and clients, not just which files moved. For the reasoning behind a change read [docs/HISTORY.md](docs/HISTORY.md); for the system as it stands read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Covers history up to `b8be171`. `python3 scripts/check_changelog.py` lists any later commit that is not yet in these notes; run it before a release and add the entry in the same change set as the work it describes. A commit that changes this file carries its own notes (it cannot link its own hash), so the check does not list it; it gets its link when the marker next moves past it.

Sections used: **Added** (new capability), **Changed** (behaviour, policy or defaults), **Fixed** (a defect corrected), **Security**, **Operations** (deployment, hosts, retention), **Documentation**.

## 2026-10-31

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
- **The gate switch stops every automatic write.** `automatic_quality_gate.enabled` used to stop only new-listing publication and contact/content refresh; program updates, engine intake and publish, and Padel intake ignored it and only took a slot from the daily cap. Their reservation now refuses while the switch is not true, the run is held ("Automatic quality hold: automatic writes are switched off") and no write is sent. The switch is on today, so normal running is unchanged. Tests: `test_gate_switch.py`. Not deployed yet.
- **The older Padel implementation is removed.** `padel_discovery`, `padel_candidate` and `queue_padel_candidate` in `company_ops.py` ran only when the engine client flag was off and had never written a packet. Padel kinds now go to the engine client only and fail with a clear message when it is not configured. Not deployed yet.
- `scripts/deploy_gateway_update.py` is retired (it left out four modules the gateway imports; it now refuses to run without an explicit flag); `scripts/verify_gateway.py` takes job types and defaults from `config/job-routes.json` and `config/model-policy.json`; `tests/test_gateway.py` reads the text default from the policy.
- Removed eight `factory.json` keys that no code reads, and three unused single-format parsers from `publishing.py`; the publication tests now call the parsers production uses.

### Documentation
- Documentation and comment review of 2026-10-30 ([b8be171](https://github.com/moldovancsaba/hetzner-nano-server/commit/b8be171)); the findings are in [docs/GAP-ANALYSIS-2026-10-30.md](docs/GAP-ANALYSIS-2026-10-30.md). Three of the 22 defects wait for an owner decision (an expired automatic packet, the gate switch on engine and program writes, the second Padel path) and one is by design (one identity for both engines).
- Added the system architecture ([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)), a benchmark and ranking index ([docs/BENCHMARKS.md](docs/BENCHMARKS.md)), code conventions ([docs/CODE-CONVENTIONS.md](docs/CODE-CONVENTIONS.md)), a dated gap analysis ([docs/GAP-ANALYSIS-2026-10-30.md](docs/GAP-ANALYSIS-2026-10-30.md)) and these release notes.
- Rewrote the README as an entry point with a documentation map and repository map; the dated round-by-round paragraphs moved to the benchmark index.
- Corrected statements that no longer matched the code across the operating, access, job-router, model-policy, retention, backlog and Paperclip documents, and added a Known limitations section to the operations and Paperclip pages.
- Added module docstrings to every Python file that lacked one, fixed misleading comments, and documented the non-obvious invariants (storage lease epoch, circuit breaker, request-header trust, error-text routing, write reservation order). No executable code changed.
- Added `scripts/check_changelog.py`.

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
