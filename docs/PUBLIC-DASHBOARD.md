# Public benchmark dashboard

Share: **https://chatbotapi.haho.ai/benchmarks/** (no login required).

The static page contains historical aggregate benchmark results, current configured defaults, a filterable registry of attempted model variants, and direct GitHub evidence links. JSON export: https://chatbotapi.haho.ai/benchmarks/results.json.

## Counting and comparisons

At publication on 28 October 2026, the evidence registry contains **41 distinct model IDs**, including unsuccessful load/inference attempts. Repeated runs count once; sizes and quantization variants count separately. This is neither the count of model families nor installed weights.

Fourteen separate historical tables cover Round 3, Round 4, Round 5 merged rankings and broader English/image evaluations, budget-limited English attempts, and preliminary/broader moderation. Do not combine scores across these cohorts. Earlier attempts remain represented in the full registry with their source links. Non-English evidence stays separate and is linked from the page.

A valid response is not necessarily a correct answer. Recognition uses 32 images in the broader set; moderation uses 41 with small per-category positive samples and mandatory human review. Historical latency is workload/profile specific. See source reports for category confidence intervals, failures and limitations.

## Refresh after testing

From the repository root:

```sh
python3 scripts/build_dashboard.py
python3 scripts/deploy_dashboard.py
```

The builder regenerates the attempted-model registry in memory using the existing evidence index builder, and exports only explicitly allowed aggregate fields. It does not export raw prompts, generated answers, images, credentials, production metrics or request identifiers. Commit the dashboard source, generated snapshot and any new benchmark evidence together so GitHub links stay useful.

The deployer uploads exactly two files to `/var/www/narimato-benchmarks`, validates the Caddy configuration and reloads only Caddy. Its first installation saves a root-only previous configuration and restores it on validation/reload failure. Existing private API routes remain authenticated. Static files have a five-minute public cache; this is a manually refreshed benchmark snapshot, not live operational monitoring. No inference or model changes are performed by publishing.

After each benchmark round, rebuild and publish this dashboard alongside the normal ranking/policy updates. The page displays the snapshot build time; individual cohorts retain their original recorded timestamps where available.
