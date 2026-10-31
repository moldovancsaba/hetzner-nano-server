# Hetzner AI servers

Source, configuration, measurements and operating documentation for two small Hetzner Cloud hosts, established 2026-10-26. Public repository: [hetzner-nano-server](https://github.com/moldovancsaba/hetzner-nano-server). Local documentation root: `/Users/Shared/Projects/hetzner`.

- **Inference host (`narimato-chatbot`)** serves small local language and vision models through one authenticated queue at `https://chatbotapi.haho.ai/v1`: text jobs for ClassScout, Habigoal and Pandora, review-assistance image jobs for Camera, and the Paperclip factory's research calls. It also publishes a [public benchmark dashboard](https://chatbotapi.haho.ai/benchmarks/) with every attempted model, failures included.
- **Paperclip host (`narimato-paperclip`)** serves https://paperclip.haho.ai behind a password gate. It runs the Paperclip company application and the ClassScout research factory: five agent roles that discover public sources, extract quoted facts, check quality and prepare listings, which an automatic gate may publish to ClassScout.

For how the pieces fit, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). For what changed and when, read [CHANGELOG.md](CHANGELOG.md).

## Start here

1. Read this file and [docs/ACCESS.md](docs/ACCESS.md) before running any command.
2. Read [AGENTS.md](AGENTS.md): it holds the standing rules for agents (credentials, test markers, model policy, retention).
3. Inspect current state before changing anything: `python3 scripts/healthcheck.py --project classscout`, or `sh scripts/server.sh status` for the inference host.
4. Integrating an application: [docs/INTEGRATION.md](docs/INTEGRATION.md). Maintaining or installing: [docs/OPERATIONS.md](docs/OPERATIONS.md). Working on the research factory: [paperclip/README.md](paperclip/README.md), then [paperclip/factory/WORKFLOWS.md](paperclip/factory/WORKFLOWS.md).
5. For decisions, evidence and open work read [docs/HISTORY.md](docs/HISTORY.md), [docs/MEASUREMENT.md](docs/MEASUREMENT.md), [docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md) and [BACKLOG.md](BACKLOG.md).

## Documentation map

| Topic | Read |
| --- | --- |
| System design, components, limits, data stores | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Release notes | [CHANGELOG.md](CHANGELOG.md) |
| Dated decisions and setup narrative | [docs/HISTORY.md](docs/HISTORY.md) |
| Access, keys, SSH, fingerprints | [docs/ACCESS.md](docs/ACCESS.md) |
| Installing and operating the inference host | [docs/OPERATIONS.md](docs/OPERATIONS.md) |
| Calling the API from an application | [docs/INTEGRATION.md](docs/INTEGRATION.md), [docs/JOB-ROUTER.md](docs/JOB-ROUTER.md) |
| Which model serves which job | [docs/MODEL-POLICY.md](docs/MODEL-POLICY.md), [docs/CHATBOT-CONTEXT.md](docs/CHATBOT-CONTEXT.md) |
| Camera image moderation (human review stays required) | [docs/CAMERA-MODERATION.md](docs/CAMERA-MODERATION.md), [docs/CAMERA-REJECTION-COVERAGE.md](docs/CAMERA-REJECTION-COVERAGE.md) |
| Personal chat (Pandora) | [docs/CHAT.md](docs/CHAT.md) |
| Experimental Hungarian text | [docs/HUNGARIAN.md](docs/HUNGARIAN.md), [docs/HUNGARIAN-FOLLOWUP.md](docs/HUNGARIAN-FOLLOWUP.md), [docs/AGENT-PROMPT-HU.md](docs/AGENT-PROMPT-HU.md) |
| Benchmarks, rankings, rounds | [docs/BENCHMARKS.md](docs/BENCHMARKS.md), [docs/PUBLIC-DASHBOARD.md](docs/PUBLIC-DASHBOARD.md), [docs/CONTINUOUS-EVALUATION.md](docs/CONTINUOUS-EVALUATION.md) |
| Model storage and retention | [docs/AUTO-MODEL-CLEANUP.md](docs/AUTO-MODEL-CLEANUP.md), [docs/DATA-RETENTION.md](docs/DATA-RETENTION.md) |
| Usage reports, alerts, watchdogs | [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) |
| Candidate models and discovery | [research/SHORTLIST.md](research/SHORTLIST.md), [research/CANDIDATES-20261029.md](research/CANDIDATES-20261029.md) |
| Paperclip host: deployment, backups, restore | [paperclip/README.md](paperclip/README.md), [paperclip/MODEL-SELECTION.md](paperclip/MODEL-SELECTION.md) |
| Research factory: workflows and acceptance | [paperclip/factory/README.md](paperclip/factory/README.md), [WORKFLOWS.md](paperclip/factory/WORKFLOWS.md), [ACCEPTANCE.md](paperclip/factory/ACCEPTANCE.md) |
| Factory subsystems | [PUBLISHING.md](paperclip/factory/PUBLISHING.md), [SEGMIND.md](paperclip/factory/SEGMIND.md), [BRAVE.md](paperclip/factory/BRAVE.md), [SLG.md](paperclip/factory/SLG.md), [CLASS-SCOUT-HANDOFF.md](paperclip/factory/CLASS-SCOUT-HANDOFF.md), [INDUSTRY-RESEARCH-20261028.md](paperclip/factory/INDUSTRY-RESEARCH-20261028.md) |
| Code conventions and comment rules | [docs/CODE-CONVENTIONS.md](docs/CODE-CONVENTIONS.md) |
| Documentation and code review of 2026-10-30 | [docs/GAP-ANALYSIS-2026-10-30.md](docs/GAP-ANALYSIS-2026-10-30.md) |

## Repository map

| Path | Contents |
| --- | --- |
| `gateway/` | The inference gateway: auth, FIFO queue, model catalog, long-context budgeting, usage and metrics stores |
| `chat/` | The Pandora personal-chat service and its token-budgeted conversation context |
| `moderation/` | Image normalization, the nine-category review policy and inference helpers used by the gateway (the standalone service is retired) |
| `operations/` | Monitor, debounced alerts, notifications and the external reachability watchdog |
| `storage/` | The hourly model cleaner |
| `research/` | The daily metadata collector for new model candidates, and the dated shortlists |
| `dashboard/` | The generated public benchmark dashboard (`index.html`, `results.json`) |
| `config/` | Deployed runtime snapshots: compose file, sanitized Caddyfile, systemd units, ranking sources, the generated model policy and the storage policy |
| `scripts/` | Health check, benchmark client, deploy and verify scripts, policy generation, dashboard build |
| `tests/` | Unit tests for the gateway, chat, policy, metrics, discovery and Hungarian route |
| `benchmarks/` | Round-by-round runners, fixtures, reports and rankings (see [docs/BENCHMARKS.md](docs/BENCHMARKS.md)) |
| `results/` | Measured results and dated verification snapshots |
| `examples/` | Example client code |
| `paperclip/` | Paperclip host: compose, Caddy, access gate, backup and restore scripts, verification evidence |
| `paperclip/factory/` | The ClassScout research factory: worker, workflows, publishing gate, engines and its tests |
| `private/` | Credentials and live sensitive configuration. Never in Git, never shared; not part of a clone |

## Ground rules

- **Credentials** live in `private/` locally and in root-only files on the servers. They never appear in Git, docs, screenshots or logs. The canonical API key store is the server file named in [docs/ACCESS.md](docs/ACCESS.md). The SSH private key stays on the owner's Mac.
- **Tests and benchmarks** must send `X-Request-Purpose: test` so they never count as production demand or keep a model installed.
- **Defaults follow the rankings.** The `auto` model for each job is the best eligible entry in its current ranking; explicit model IDs are deliberate overrides. A test round is finished only when ranking, generated policy, installed models, deployment, API discovery and documentation agree ([docs/MODEL-POLICY.md](docs/MODEL-POLICY.md)).
- **No customer content is stored.** Request bodies live in memory only, finished results expire after five minutes or on client deletion, and nothing from production is used for training ([docs/DATA-RETENTION.md](docs/DATA-RETENTION.md)).
- **Human review stays authoritative** for Camera moderation: results are review signals, never automatic approval or rejection.
- **Language workstreams are separate.** English, image, moderation and each non-English language are ranked and approved on their own evidence.

## Verifying a change

```sh
python3 scripts/healthcheck.py --project classscout        # key rejection and authentication (read-only)
python3 scripts/verify_model_policy.py                      # defaults, discovery and overrides through the public API
python3 scripts/promote_rankings.py --check                 # generated policy matches the evidence
python3 -m unittest discover -s tests                       # gateway, chat, policy and metrics unit tests
cd paperclip/factory && python3 -m unittest discover -p 'test_*.py'   # factory tests
```

The unit tests need Pillow, and the gateway tests also need the `tokenizers` package; the factory tests need Pillow. `verify_*` scripts call the public API with test-purpose requests and write evidence under `results/`; read a script's docstring before running it against production, because some deploy and verify scripts are single use or have known stale assertions (see [docs/OPERATIONS.md](docs/OPERATIONS.md#known-limitations)).
