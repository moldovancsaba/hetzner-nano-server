# Documentation and code-comment gap analysis, 2026-10-30

A review of this repository's documentation, code comments, architecture description and release notes, with what was found, what was changed and what was deliberately left alone. It is a dated record: the fixes it lists are made, and the open items it lists belong on the repository's project board.

## Scope and method

- **Examined:** 197 tracked Python files, 74 tracked Markdown documents (38 outside the benchmark and result archives), the `config/` snapshots and the 39 commits of history.
- **Mechanical checks:** every Markdown link and backticked path against the tracked files; comment, docstring and module-docstring coverage of every Python file; repeated figures compared across documents.
- **Verification against code:** two read-only passes mapped the inference host and the Paperclip host and compared each concrete claim in the documents (numbers, limits, schedules, endpoints, file names, counts) with the code or configuration. Findings were re-checked against the source before any edit; one claim in a first report (11 gate checks) was wrong and the code says 12.
- **Safety of the code edits:** every changed Python file was compared with `HEAD` after removing docstrings (`scripts/check_comment_only.py`). Of the 88 changed tracked files, 87 differ only in comments and docstrings; the 88th, `tests/test_hungarian_api.py`, has `unittest.main()` moved from the middle of the file to the end so the second test class runs when the file is executed directly. The 364 factory tests pass and the `tests/` directory gives the same results as `HEAD` (one failure and two errors that need the real Pillow and `tokenizers` packages). Nothing was deployed, so the servers still run the previous (comment-different, behaviour-identical) files.

## Summary

| Area | Gap found | Result |
| --- | --- | --- |
| Architecture | No document describing components, request flow, state, limits, the factory pipeline or its database | Added [ARCHITECTURE.md](ARCHITECTURE.md) |
| README | Grew as a dated log: inventory, dated round results, stale counts, a file map that omitted most directories, no documentation map | Rewritten as an entry point with a documentation map and a repository map; round results moved to [BENCHMARKS.md](BENCHMARKS.md) |
| Release notes | None; history existed only as narrative in HISTORY.md | Added [CHANGELOG.md](../CHANGELOG.md) covering all 39 commits, plus `scripts/check_changelog.py` that reports any commit the notes miss |
| Conventions | Two code styles and the comment practice were nowhere stated | Added [CODE-CONVENTIONS.md](CODE-CONVENTIONS.md) |
| Document contradictions | Statements wrong or stale against the code, and documents contradicting each other | Corrected (details below) |
| Module docstrings | 52 of 197 Python files had none | All have one |
| Misleading comments | Comments and docstrings that contradicted or misdescribed the code | Corrected |
| Missing explanation | Invariants, boundaries and ordering rules with no comment | Commented |
| Behaviour defects found while checking | 22 | Documented, not changed (below) |

## Documentation contradictions fixed

| Where | What was wrong | Now |
| --- | --- | --- |
| README, `paperclip/README.md`, `factory/README.md`, `WORKFLOWS.md` | Five workflows, thirteen or eighteen routines, four native routines | 19 routines (17 scheduled, 2 manual), from `workflows.json`; the schedule table is rebuilt from it |
| `WORKFLOWS.md`, `PUBLISHING.md`, `paperclip/README.md` | Human approval described as the live publication path; policy pointers at v3 and v4 | The automatic gate is the live mode; a new section describes `classscout-auto-v6` (12 checks for a new listing, 7 for a content update, the daily cap, expiry, verification); the human path is described as the mode when the gate is off |
| `WORKFLOWS.md` | Wrong role for `verify_catalog`; routine schedules out of date; the gate switch said to govern every write path | Corrected to the code; the switch's real scope stated |
| `PUBLISHING.md`, `SLG.md`, `CLASS-SCOUT-HANDOFF.md` | Wrong ClassScout origin; "only Classes" while camps and months are supported; "no placeholder image" while the category banner is accepted; "no restore drill" while one exists | Corrected |
| `SEGMIND.md`, `BRAVE.md` | Segmind scope narrower than the code; Brave candidate count, locales and purposes out of date | Corrected |
| Documents naming git-ignored deliverables | Links to four files that are kept local and not in Git | Say so plainly instead of linking |
| `JOB-ROUTER.md` | Discovery response shown as `job-router.v1`; no Paperclip tenant or `text_chat_hu`; per-tenant limit and native timeout wrong; protection "for 14 days" | `job-router.v2` with its fields, the full tenant and task matrix, the limit of 4 queued plus running (1 for Paperclip), the 900 s text timeout, three days |
| `OBSERVABILITY.md`, `MODEL-POLICY.md`, `ACCESS.md`, `OPERATIONS.md`, `BACKLOG.md` | "Top five and 14 days" retention; MiniCPM 1B named as the current default; keys "in Caddy"; rotation by staging two keys in Caddy; "four waiting jobs"; verify "both" keys; alert coverage overstated; variant count 38 | Top three and three days; Q5_K_M is current; keys live in the gateway, rotation has no overlap; counts and coverage matched to the code; 52 variants after Round 6 |
| `CHATBOT-CONTEXT.md`, `INTEGRATION.md`, `CHAT.md`, `CAMERA-MODERATION.md` | The 1536-token reservation said to include the reply; chat body limit said to be 30 x 24,000 characters; Retry-After stated as 10 s | Reservation is in addition to the reply; Caddy's 128 KB limit is the effective one; Retry-After is 2 s for the upload slot, 10 s otherwise |
| `CONTINUOUS-EVALUATION.md` | Reads said to be bounded by an allowlist | The allowlist is checked on the first URL only and is not re-applied on redirects |
| `IMPROVEMENTS.md` | A 2026-10-26 list saying there was no restore drill, no isolation, no monitoring | Rewritten: what is still open, what is done and where it is documented |
| `AGENTS.md` | "Live Caddy config contains keys" | Local copies of the live Caddy config are sensitive; Caddy holds no keys |
| `config/Caddyfile.example` | "Private API routes remain authenticated" | Caddy does no authentication; the gateway and chat server do |
| `AUTO-MODEL-CLEANUP.md` | No statement of which policy keys are enforced | A table: five keys are read; the rest are informational |
| `HISTORY.md` | Presented older figures without saying they are superseded | A header states it is dated narrative; entries are not rewritten |

Cross-references were already sound: no broken Markdown link existed, and the 21 backticked paths that do not resolve point at other repositories or at files generated on the server.

## Code comments fixed or added

- **Misleading or stale, corrected:** `moderation/server.py` (most of the file is the retired service; only two functions are live), `moderation/policy.py` (the model constant is a legacy default), `moderation/deploy.py`, `scripts/retire_declined_models.py` (exits under the current storage policy), `storage/cleaner.py` (one value is pinned, not bounded), `gateway/server.py` (a change-log remark in a comment), `paperclip/factory/worker.py` ("no publishing" while it dispatches automatic writes), `publishing.py` and `refresh.py` ("human-approved" for paths that are now automatic), `refresh.py` and `segmind.py` (field lists narrower than the code), `search_workflow.py` (a regex alternative no code emits), `restore-drill.py` (fixed values presented as measurements), the Caddy file comment.
- **Added where a reader would otherwise be misled:** the storage-lease epoch and the lease itself, the circuit that never closes until a restart, the loopback-only maintenance endpoint, the start-up snapshot of the default model, the tokenizer that approximates every model's token count, debounce and rank sentinels in the policy and alert code, single-use and incomplete deploy scripts, the OOM-critical cache limits, the request-header trust boundary of the access gate, the field-injection defence in `catalog.field`, escaping of untrusted text before it is posted, error-text-dependent routing, why HTTP 207 and 422 return their body, the reserve-before-send ordering and the uncertain and held outcomes, the receipt literals, import cycles, the Padel token reuse, and the code that is dead or kept only for its tests.
- **Module docstrings:** 52 files had none (31 test files, 19 benchmark scripts, the chat server, the health check); all now state what they do or test. Benchmark scripts are described mechanically and as a historical record only where the round's own report says so.

## Coverage after the changes

| Area | Comment lines | Defs with a docstring or adjacent comment | Module docstrings |
| --- | --- | --- | --- |
| `paperclip/factory` code | 74 to 141 | 10% to 13% | 36 of 36 |
| `paperclip/factory` tests | 3 | under 1% | 2 of 18 to 18 of 18 |
| `gateway/` | 8 to 25 | 5% to 11% | 7 of 7 |
| `scripts/` | 6 to 10 | 3% to 6% | 19 of 20 to 20 of 20 |
| `tests/` | 3 | 1% | 1 of 15 to 15 of 15 |
| `benchmarks/` | 40 | under 1% | 63 of 83 to 83 of 83 |

Module-level and boundary documentation is now complete. Function-level documentation is still thin by design: the dense house style puts many short functions in each file, and the conventions ask for comments on what is not obvious rather than on every function. A function-by-function pass for the public entry points of the factory is the next step if that standard is wanted.

## Defects found while checking, not changed

These are behaviour, not documentation, so they were recorded where a reader meets them (the Known limitations sections of [OPERATIONS.md](OPERATIONS.md#known-limitations) and [../paperclip/README.md](../paperclip/README.md#known-limitations)) and are listed here with a suggested handling. None was verified by running it against production.

| # | Where | Effect | Suggested handling |
| --- | --- | --- | --- |
| 1 | `paperclip/factory/provision.py:36` | Re-running it writes a `factory.json` without `remote_llm` (the Segmind lane goes off), and writes `search_candidate_limit` as 2 when no earlier file exists | Preserve `remote_llm` and the limit |
| 2 | `paperclip/snapshot.sh:17-28` | The recovery bundle does not contain `/etc/paperclip-segmind.env` | Add it to the bundle list |
| 3 | `factory/engine_ops.py:7-17`, `padel.py:6-8` | One cached Padel SSO token is also sent to the Sportolok engine | Confirm both engines are meant to accept it, or cache per audience |
| 4 | `factory/search_workflow.py:81` | `research_backlog` reads one unpaged page of 500 issues, so the discovery limit can be wrong above 500 active tasks | Use `issue_pages` |
| 5 | `factory/publishing.py:281`, `pipeline.py:57`, `refresh.py:78` | A packet older than 48 h raises "approval expired" on every re-run until the brief changes, also in automatic mode (read from the code, not reproduced) | Decide the expiry rule for automatic mode |
| 6 | `paperclip/restore-drill.py:36,61` | Three recorded assertions are constants, not measurements | Measure them or label them as declarations in the output |
| 7 | `factory/program_updates.py:85`, `engine_ops.py:87`, `padel.py:66` | These write paths ignore the gate switch and have no human mode; they share the daily cap | Decide whether the switch should cover them |
| 8 | `paperclip/configure-slg.py:23` | Ends with `setup(True)`, which re-enables every scheduled trigger | Enable only the SLG routines |
| 9 | `factory/business_metrics.py:118` | The billing label is always "Free local models" although a metered lane exists | Derive it from the ledger |
| 10 | `factory.json` | Eight keys are never read (`pilot_brand`, `outreach_enabled`, `max_source_pages_per_task`, `automatic_quality_gate.policy`, `growth_mode.coverage`, `.campaign`, `.active_research_limit`, `sales.delivery_enabled`) | Remove or wire them |
| 11 | `company_ops.py` and `engine_ops.py` | Two code paths for Padel discovery and candidates | Remove the unused one |
| 12 | `gateway/server.py` `status()` | `per_service_limit` is always 4, but the Paperclip tenant is limited to 1 | Report the tenant's own limit |
| 13 | `operations/monitor.py:25` against the 900 s text timeout | The 300 s "stuck" alert can fire during a valid long job | Align the threshold with the profile timeout |
| 14 | `operations/monitor.py`, `external_watchdog.py` | Their own polls add about 2,880 events a day each, about 172,800 of the 200,000-row metrics cap over 30 days | Exclude them from the cap or count them separately |
| 15 | `storage/cleaner.py` | Cleaner reports are never pruned (about 24 files a day) | Add retention |
| 16 | `scripts/deploy_gateway_update.py` | Ships five files and omits four modules the gateway imports; other deploy scripts are single use | Retire it or give it the full file list; no script installs the cleaner, collector, monitor or their units |
| 17 | `scripts/verify_gateway.py:21,38` | Asserts old job types and model defaults, so it fails against today's API | Derive expectations from the live policy |
| 18 | `tests/test_gateway.py` | Hard-codes the text default; needs the real tokenizer | Read the default from the policy; document the dependency |
| 19 | `research/collect.py:61-63` | The host allowlist is checked on the first URL and not on redirect targets | Re-check after redirects |
| 20 | `chat/server.py` | The 256 KiB body check is unreachable because Caddy caps `/chat` at 128 KB | Align the two limits |
| 21 | `config/tested-models.json` | Lags the generated policy by three `ranked_tasks` entries | Rebuild with `scripts/build_tested_model_index.py` |
| 22 | `paperclip/local-ai.json:11`, `factory/test_publishing.py` | A stale approval-gated sentence in a config snapshot; tests that exercise code the production path no longer uses | Update the snapshot text; test `formats` instead |

Also noted: `BACKLOG.md` states that it is the repository's task backlog, while planning and status are meant to live on the project board. That is an owner decision about where the backlog lives, so it was left as written.

## Keeping it from drifting

- [CODE-CONVENTIONS.md](CODE-CONVENTIONS.md) states the comment rules, the one-source rule for documents, and that an architecture or release-note change ships in the same commit as the work.
- `python3 scripts/check_changelog.py` fails when a commit is missing from the release notes; `python3 scripts/check_comment_only.py` proves a documentation-only change did not touch code.
- The documents that restate figures now link to where the figure is generated or enforced ([ARCHITECTURE.md](ARCHITECTURE.md#where-a-fact-is-decided)).
