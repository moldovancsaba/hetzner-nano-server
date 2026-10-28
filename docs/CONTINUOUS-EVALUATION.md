# Continuous model discovery and evaluation plan

## What is scheduled now

A server-side systemd timer collects **public metadata only** every day at **03:30 Europe/Budapest**, with up to 15 minutes of randomized delay. The timer is persistent, so a missed run is caught up after downtime. It does not download weights, run inference, change rankings/defaults, capture live requests or send external messages.

Units: `narimato-model-discovery.timer` and `narimato-model-discovery.service`. Code/config: `/opt/narimato-discovery`. Metadata state: `/var/lib/narimato-model-discovery` (restricted service directory). The first verified run used all 12 configured feeds and observed 658 unique source/model records, with 24 candidates remaining after the current shortlist/scope filters. See the dated [initial report](../results/discovery/initial-report.json); counts can change on subsequent runs.

An independent hourly [model cleaner](AUTO-MODEL-CLEANUP.md) now retains top-three-per-task or 14-day production-used weights. It is not part of discovery. Pause it before operator download/native benchmark experiments, then restore/verify production and re-enable it.

The collector is a low-priority, restricted service with no Docker privileges or API keys, 10% CPU quota, 160 MiB memory cap and eight-minute execution timeout. Public outbound reads are bounded to allowlisted source hosts, 20 seconds/request and 16 MiB/response. Local Ollama inventory is read-only metadata. No remote code, README instruction, model binary, dataset or script is downloaded/executed.

## Sources and confidence

| Source | Collected information | What it does not establish |
| --- | --- | --- |
| Hugging Face official publisher feeds | IDs, revisions, tags, model task, license tags, popularity and size estimates | Publisher tags do not prove server compatibility, accuracy or commercial suitability |
| Recent Hugging Face GGUF/vision feeds | New artifacts and conversions, including community packages | A conversion is not a verified publisher release or an approved download |
| OpenRouter public model catalog | Model IDs, modalities, context, supported parameters, Hugging Face references when supplied | A hosted endpoint is not proof that weights can run locally |
| Ollama official library | New family names and source links | A family listing does not select a usable tiny tag or quantization |
| Ollama / llama.cpp official GitHub releases | Runtime release version/date/link | An upstream release is not an installed upgrade or automatic permission to retest |

Primary source documentation: [Hugging Face Hub API](https://huggingface.co/docs/hub/api), [OpenRouter model catalog API](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties), [Ollama library](https://ollama.com/library), [Ollama releases](https://github.com/ollama/ollama/releases), [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases).

Publisher allowlist currently includes LiquidAI, IBM Granite, Qwen, Google, Mistral and HuggingFaceTB. This identifies the account source; it does not approve its license or any claim. API responses are treated as untrusted data, never instructions.

## Discovery state and shortlist

The SQLite registry accumulates model metadata with first/last seen and upstream revision; it is capped at 10,000 records. Daily compressed **normalized metadata** snapshots expire after 30 days and are capped at 50 MiB. Test/decline decisions and actual benchmark evidence are separately versioned and never depend on this disposable discovery history.

`latest.json` contains source status, revision changes, runtime releases, installed-model/storage metadata and a ranked review shortlist. `last-success.json` preserves the most recent run with any successful source. Partial source failure is explicit (`degraded`); a wholly failed run exits nonzero and keeps the earlier registry/last-success artifact. One source failing does not mean previously known models disappeared.

Heuristic scores favor small parameter estimates, GGUF packaging, known publishers and available license metadata. Speech-only, embeddings and time-series tasks are excluded from the current text/vision shortlist. Unknown size/license/runtime remains a review issue. A 1B name is not a measured memory budget; projector, KV cache, encoder, active/total parameters and quantization matter. Popularity and context-window length never substitute for quality tests.

A metadata match against `config/tested-models.json` suppresses unchanged known families from the fresh shortlist. Family matching is heuristic; operators must check whether a fine-tune, quantization or revision is genuinely new. Revision changes and runtime releases are review signals; failed models are not automatically retried daily. `config/model-decisions.json` preserves reviewed declines and re-test reasons.

## Proposed human review/test cadence

Discovery and safe weight cleanup are automatically scheduled; model inference tests are not. The following is an operating plan, not an enabled unattended benchmark timer:

- **Weekly:** review the latest shortlist and source health; select at most two candidates for a stated job. Reserve roughly 30–45 minutes for provenance/license/artifact review.
- **Fortnightly:** use an approved low-traffic maintenance window for eligible candidates. Drain/disable public generation first; one candidate at a time, bounded time/download budget, restore all services afterward.
- **Monthly:** review real project holdouts, false negatives/alarms, queue waiting, storage budget, alternatives actually used and criteria that are too weak. No live content is collected for this review by default.

A reasonable proposed test window is Saturday 04:00 Budapest time after the discovery window, but it is **not scheduled**. CPU-only testing can interrupt chat; a future unattended benchmark runner must prove isolation, timeout recovery and restoration before it receives its own timer.

## Test gates

1. **Purpose and novelty:** choose English structured text, general image recognition, moderation, or an independently named language/task. Check past decisions and confirm what changed.
2. **Source and rights:** verify publisher/upstream, license/gating, exact artifact revision and checksums. No executable remote code or pickle-style model loading is enabled by discovery. Do not claim all open weights have the same license.
3. **Resource preflight:** 2 ARM64 CPUs, 2800 MiB Ollama cap, 2048 configured context and measured image profile. Target at least 8 GiB free disk; never cross the 4 GiB hard floor during download/test. Account for projected temporary weights and existing rollback/pins. Do not solve a failure by silently raising memory limits or adding swap.
4. **Eligibility:** load and make a real text/image request, validate actual output/schema, memory/OOM events and cleanup. A tag listing alone is not a successful test. Stop on repeated OOM or runtime failure.
5. **Comparable quality:** rerun the current winner and candidate against frozen regression fixtures plus approved unseen project holdouts. Keep expected values separate from output schema. Score valid format, correct values, tool calls where relevant, truncation and abstentions separately. Evaluate all nine moderation categories individually with positives, negatives and ambiguity; do not reward all-null outputs as safe decisions.
6. **Performance:** measure first load, warm generation, new-image prefill, unload and mixed text/image switching. Record queue waiting separately. Capture real peak/cgroup memory and OOM deltas, not just a post-response sample. Meaningful p95 estimates need enough independent requests; repeated deterministic fixtures are not new examples.
7. **Decision:** accept, decline or defer with per-task evidence and reason. Delete newly declined candidate weights after recording digests/results. Record runtime/profile failures as eligibility failures, not bad accuracy scores.
8. **Default update:** follow [MODEL-POLICY.md](MODEL-POLICY.md). Update canonical rankings/source pointers; run `scripts/promote_rankings.py --write` and `--check`, install matching winners, deploy the generated policy, and verify real auto jobs, explicit alternatives, shared queue, keys and Pandora. No previous winner should remain the default merely because it was already deployed.
9. **Finish:** rebuild `config/tested-models.json`, copy it to `/opt/narimato-discovery/tested-models.json`, preserve the decision and refresh docs/backlog. Keep approved benchmark evidence; remove temporary inputs and unneeded candidate weights; confirm free disk and healthy services.

Current benchmark gaps are tracked in [BACKLOG.md](../BACKLOG.md), including real project holdouts, photographic forbidden-content examples, explicit acts/violence coverage, independent labels and peak-memory measurement. The initial two-image vision ranking is useful for screening, not a production accuracy certificate.

## Benchmark data versus training data

The owner approved retaining **curated, explicitly approved datasets and labels only** for training. Production Camera images and conversations are never captured into a dataset. Training fixtures and held-out evaluation fixtures must be different splits with immutable manifests; do not train on the benchmark and then present its score as unseen performance. Existing research/test fixtures are not automatically approved for training or redistribution.

This server is for inference and lightweight evaluation; actual fine-tuning/training needs a separate compute/storage plan. No fine-tuning is performed by discovery or this scheduled job. Keep dataset provenance, approvals, versions, labels, training configuration, adapter/model digest and evaluation outcomes; see [retention policy](DATA-RETENTION.md).

## Operator commands

```sh
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'systemctl list-timers narimato-model-discovery.timer --no-pager'
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'journalctl -u narimato-model-discovery.service -n 20 --no-pager'
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'cat /var/lib/narimato-model-discovery/latest.json'
```

Run collection manually with `systemctl start narimato-model-discovery.service`; it is still metadata-only. Disable scheduling with `systemctl disable --now narimato-model-discovery.timer`. To deploy collector changes, copy reviewed code/config/index to `/opt/narimato-discovery`; reload systemd only when units change. Never grant this collector the project API keys, Docker group or GitHub write credentials.

Ongoing reports are server-local; the linked GitHub report is a dated published snapshot. No automatic GitHub push, email, Slack message or Codex-app automation was created. Meaningful failure notification is a backlog item pending an authorized destination.
