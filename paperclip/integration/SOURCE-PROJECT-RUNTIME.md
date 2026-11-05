# Dedicated source-only projects

BOS, LA and the SLG workspaces use dedicated source projects, isolated from native catalog and CRM execution. Installing this runtime does not register a project or authorize its source policy. Existing NYC and Management projects retain their ordinary paths.

## Admission and execution

`source_exchange.source_only_projects` contains the explicitly reviewed project plans. A plan binds its exact enrolled scope, `source-only` mode, independent review reference, application-owned query-policy digest, bounded public queries, country/language and minimum dispatch interval. The native project routing label must be `Sources: <application>/<client>`. Source enrollment, project-policy receipt and distinct scoped producer credential are required before any task can execute. Missing runtime configuration for an enrolled source-only scope holds the task; it cannot fall through into a business workflow.

Only the existing Search role may execute `exchange_source_search`, with the exact scope, review reference and one approved query. Native publication, research, quality, support and CRM workflows are rejected before checkout or business dependencies. The search lane uses the existing global reservation, cooldown, account reserve and daily/monthly limits. Unsupported provider locales hold before a request; no default locale silently substitutes for the reviewed policy.

The search response stays in memory. Pages are fetched independently through the normal public transport; only page-derived URL/title/hash/time and accepted public offer evidence are retained. SLG source projects do not inherit the children's-page discovery filter. ClassScout sources retain that filter, and OpenClaw independently checks ownership, youth suitability and destination-resolved geography. A failed public-offer export is not reported as an exported source page. These tasks create no native publication, research, quality or CRM handoff.

## Coordination and recovery

The existing autonomy turn shares its exchange deadline with optional source dispatch. The dispatcher starts no native request unless its fixed timeout fits the remaining allowance, and performs at most one native API request per turn. It checks the existing search backlog and shared allowance before queuing work. It rotates reviewed project scopes and respects their dispatch interval; a completed task readback is saved in its own turn before another task is considered.

The original native request and deterministic operation UUID are saved before task creation. A lost reply retains that exact intent and next-attempt time; retries never create a replacement identity. Exact company, project, description, title, assignee and task ID must match before saving the immutable receipt. Receipt history remains separate from the rotating project cursor. Changed policy or scope holds an original intent for reconciliation. Ordinary research-queue saturation cannot block source-only tasks that create no research draft; publication priority, FIFO ordering and the shared search reservation remain intact.

No new role, timer, search account, quota, model lane or notification is added. New source tasks begin only after the exact source-project/query-policy enrollment review. Destination permissions, candidate imports, legacy-writer handoff and live delivery require their separate gates.

## Release and acceptance

Use `ops/deploy_factory.py --source-project-runtime` with the exact current worker, autonomy, search and exchange-module digests. Supply the current source runtime digest if its module already exists. The helper applies bounded explicit source patches to the current host files and preserves unrelated work. It compiles every resulting module, verifies process-level idleness, takes a consistent private backup and checks service health. Failed startup restores code only; newer business/receipt databases are never overwritten. Runtime project configuration and schedules remain unchanged.

The patch specification is `ops/source_project_patches.json`. Tests exercise both current native source variants and exact staged repository snapshots, keeping unrelated in-progress source changes out of the release. Scoped admission, role refusal, private query rejection, shared allowance, original task replay, wrong receipt refusal, single-request turns, fetched-page evidence, refused exports and disabled behavior are covered without a paid search or production business job. Natural source yield and destination results require later observed evidence.
