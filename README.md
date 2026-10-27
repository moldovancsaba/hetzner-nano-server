# Hetzner AI server: agent starting point

Established 2026-10-26. Private GitHub repository: [hetzner-nano-server](https://github.com/moldovancsaba/hetzner-nano-server).

Local documentation root: `/Users/Shared/Projects/hetzner`.

## Start here

1. Read this file and `docs/ACCESS.md` before running commands.
2. For application integration, read `docs/INTEGRATION.md`.
3. For maintenance or installation, read `docs/OPERATIONS.md` and inspect current state first.
4. Run `python3 scripts/healthcheck.py --project classscout` or use `habigoal`.
5. Read `docs/HISTORY.md`, `docs/MEASUREMENT.md`, and `docs/IMPROVEMENTS.md` for decisions, evidence, and outstanding work.

## Personal chat

Open https://chatbotapi.haho.ai/chat/ and enter the owner-selected secret (no username). See docs/CHAT.md; private/chat-access.txt stores access details.

## Inventory

| Item | Value |
| --- | --- |
| Server name | narimato-chatbot |
| Provider / location | Hetzner Cloud / Falkenstein, Germany |
| Plan | CAX11: 2 shared ARM64 vCPUs, 4 GB RAM, 40 GB disk |
| Public IPv4 | 2.31.100.246 |
| Selected image | Docker CE, Ubuntu 24.04 base |
| API base URL | https://chatbotapi.haho.ai/v1 |
| Model | qwen3:1.7b; model ID 8f68893c685c; quantized download about 1.4 GB |
| Runtime | Ollama in Docker; Caddy on the host for HTTPS/authentication |
| Runtime directory | /opt/narimato-ai |
| Container | narimato-ollama |
| DNS | GoDaddy; A record chatbotapi -> 2.31.100.246, TTL 600 seconds |
| Consumers | Habigoal and ClassScout, hosted on Vercel |

## Connect and inspect

These commands run on the owner's Mac, not inside this documentation directory's own shell session:

```sh
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246
```

If the key is locked, the owner runs the following locally and enters the passphrase privately:

```sh
ssh-add --apple-use-keychain /Users/chappie/.ssh/hetzner_ai
```

Run one remote command:

```sh
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'docker ps; free -h; df -h /'
```

Or use `sh scripts/server.sh status` and `sh scripts/server.sh logs`. Local terminal automation in the original chat required `/bin/sh`, login disabled, working directory `/`; its stale default workspace no longer existed. This was a local execution issue, not a server failure.

## Credentials

`private/api-keys.json` contains the actual independent Habigoal and ClassScout bearer keys. It is a restricted local credential snapshot. `private/Caddyfile.live` also contains bearer keys. Neither belongs in Git, shared docs, screenshots, or logs. The server's `/opt/narimato-ai/api-keys.json` is the canonical source; refresh local copies after rotation.

The SSH private key stays at `/Users/chappie/.ssh/hetzner_ai`; it has not been copied here. A private key passphrase is not recorded. See `docs/ACCESS.md` for fingerprints and access boundaries.

ClassScout's key was added to `/Users/Shared/Projects/classscout/.env.local` as `LOCAL_AI_API_KEY`, with file mode 600. Git ignore and untracked status were verified. No Vercel Production environment was changed by this setup. Existing unrelated `OLLAMA_API_KEY` values must not substitute for the project key.

## Current behavior

- Public bearer API routes: `/v1/models` and `/v1/chat/completions`. `/chat/` provides a separate password-only personal chat.
- Every public API call requires `Authorization: Bearer <project key>`.
- `/v1` by itself returns 401; this is not a health check or a user interface.
- Ollama is bound to host loopback `127.0.0.1:11434`, not the public network.
- One active generation, queue limit 8, one loaded model, 2,048-token configured context, 30-minute idle model retention.
- Container cap: 2 CPUs and 2,800 MiB RAM. Persistent model storage: Docker volume `narimato-ai_ollama`.
- Send `reasoning_effort: "none"` for short direct responses. Set modest output limits.
- Host firewall allows TCP 22, 80, 443 on IPv4 and IPv6. No public inference port.

## What is and is not complete

Server, DNS, trusted HTTPS, both authentication keys, native inference, and OpenAI-compatible chat were verified. Initial baseline synthetic benchmark: 5/5 valid JSON, 3/5 strict expected-value passes, median 1.37 s; see docs/MEASUREMENT.md for the wrong arithmetic answer and the underspecified language format. Automatic container restart and Caddy service startup are configured. Production application integration, application task evaluation, rate limiting, alerting, restore testing, and capacity testing remain separate work. A single small CPU model is not proven suitable for every project task.

## Capability benchmark

Latest expanded findings: [English ranking](benchmarks/rankings/ENGLISH.md), [image analytics ranking](benchmarks/rankings/IMAGES.md), and [new candidate test report](benchmarks/round3/REPORT.md). These are separate workstreams. Eleven additional model variants were attempted; candidate weights were removed after evaluation and Qwen3 remains deployed.

Non-English capabilities are managed independently: [language-specific evaluation](benchmarks/non-english/REPORT.md). English scores exclude non-English tests. Each language and task requires its own model choice and acceptance.

Earlier round: [separate image and text/chat results](benchmarks/round2/REPORT.md). SmolVLM2 2.2B Q4 and Granite Vision passed the image checks under measured image-specific profiles. Granite 4 1B hybrid is a promising English structured-task candidate. Gemma 4 was attempted but could not complete image inference under the current limits. Qwen3 remains deployed.

See [the measured model comparison](benchmarks/capabilities/REPORT.md) for seven candidate models, actual unload/load timings, real Atlas/OSM inputs, image tests, raw outputs and integration guidance. Qwen3 1.7B remains the default. Candidate models are also downloaded; they share the one-model memory limit.

## File map

- `config/compose.yaml`: deployed runtime snapshot with image digest pinned.
- `config/Caddyfile.example`: sanitized HTTPS/authentication template.
- `private/`: actual credentials and live sensitive configuration; do not share.
- `scripts/healthcheck.py`: test no-key rejection and project authentication.
- `scripts/benchmark.py`: small sequential latency/correctness test; writes JSON results.
- `scripts/server.sh`: SSH status/log/restart helper; no destructive default.
- `results/`: measured results and dated infrastructure snapshot.
- `docs/`: history, access, integration, operations, measurements, improvements.

This repository includes documentation, source, sanitized configuration, benchmark fixtures, and measured results. Actual credentials and live sensitive configuration remain local in the ignored `private/` directory; they are not included in a clone. Authorized agents must obtain the correct project credentials from the owner or the canonical server files described in [Access](docs/ACCESS.md). The SSH private key stays on the owner’s Mac. `.gitignore` does not encrypt credentials or prevent manual upload.
