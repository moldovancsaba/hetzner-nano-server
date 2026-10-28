# Round 4 — ten new candidates

28 October 2026. Start with [the report](REPORT.md), [candidate sources](plan.json), [source metadata](source-metadata.json), [raw results](results.json), and [merged rankings](rankings.json).

Five text and five still-image candidates were attempted. This is independent of moderation, non-English, movies and training. Seven completed their quality suites; two LFM3 artifacts were incompatible with this runtime, and d1-omni did not support the generation endpoint. Valid JSON and correct expected values are separate scores.

## Workflow used

1. Read repository AGENTS.md and continuous-evaluation/model-policy guides. Check prior model/artifact decisions and review publisher/license metadata.
2. Stage run.py and plan.json in `/opt/narimato-benchmarks/round4` on the inference host. Copy the round3 fixtures module, listing/OSM JSON, image-cases.json and four PNG fixtures into the sibling round3 directory. Never substitute customer payloads.
3. Run with the host Python under a bounded one-shot service. The runner pauses cleanup, drains/acquires the gateway maintenance lease, renews it during serial native tests, records memory/OOM/digests/results, removes only temporary candidate packages, restores Granite, releases the lease and resumes cleanup. New production inference is temporarily refused during this window.
4. Copy results.json back and run `python3 benchmarks/round4/report.py`. This merges eligible completed candidates into the historical independent rankings. Fresh winner controls remain separate. See report limitations before comparing raw image scores across rounds.
5. Point config/ranking-sources.json at this round and include its digest evidence. Rebuild policy with `python3 scripts/promote_rankings.py --write`, then `--check`. Preserve independently verified 8K default profiles. Rebuild the tested index.
6. Review winners and artifact digests before applying deploy.py with reviewed model-policy.json, tested-models.json and results.json. It retains newly tested top-five choices, verifies default digests, atomically updates policy and refreshes discovery's tested index. It does not change the runtime or raise memory limits.
7. Run verify.py and verify_alternatives.py locally using ignored project credentials. All inference checks carry X-Request-Purpose: test. They verify actual response model IDs, consume/delete synthetic jobs, then restore default text residency.
8. Check services/timers/free disk, remove temporary server image fixtures, retain metadata/evidence, scan staged files for credentials, and publish reviewed documentation.

This is an operator-run screening experiment, not an unattended benchmark scheduler or a proven crash-recovery system. If interrupted, inspect native running work before releasing maintenance; restore service health and the cleanup timer explicitly. No production data or newly approved training dataset was collected.
