# Operations and recovery

## Shared inference gateway

Text, Camera image jobs and Pandora now pass through `narimato-gateway`. See [job-router operations](JOB-ROUTER.md#operations-and-changing-assignments). The former standalone moderation service stays disabled. Drain queued work before maintenance; restart loses in-memory jobs. If the gateway opens its upstream-uncertain circuit, inspect/stop unfinished inference before restarting it. The circuit never resets on its own and has no reset endpoint; only a restart of `narimato-gateway` clears it (see [JOB-ROUTER.md](JOB-ROUTER.md#queue-policy-and-resource-management)). Direct native benchmark/generation calls bypass scheduling and should not run alongside production traffic.

## Inspect before changing

```sh
sh scripts/server.sh status
sh scripts/server.sh logs
python3 scripts/healthcheck.py --project classscout
```

Runtime source: server `/opt/narimato-ai/compose.yaml`. Saved local copy: config/compose.yaml. Treat local config as a dated snapshot until compared with the server. Inspect current changes made by other agents before overwriting. Caddy's active source is `/etc/caddy/Caddyfile`; the root-only copy in /opt must be synchronized after changes.

## Maintenance commands (on server)

```sh
cd /opt/narimato-ai
docker compose config --quiet
docker compose ps
docker logs --tail 100 narimato-ollama
journalctl -u caddy -n 100 --no-pager
free -h
df -h /
docker stats --no-stream
ss -lntup
ufw status
```

Restart container: `docker compose restart ollama`. Recreate after config change: `docker compose up -d`. For HTTPS changes: `caddy validate --config /etc/caddy/Caddyfile` then `systemctl reload caddy`. Validate before reload; never print the live config to a shared log. Restart drops active generation; schedule with the owner if applications rely on it.

## Installing tools or models

Use SSH and apt for host packages. Keep application runtimes isolated in Docker. Inspect disk/memory first. Do not expose a new Docker port on all interfaces. Pin image digests, record package/model versions, and test changes using the benchmark before switching consumers. Pulling an extra model uses disk; loading two models would exceed the intended memory plan. Keep OLLAMA_MAX_LOADED_MODELS=1.

New model example (operator chooses a tested small candidate): `docker exec narimato-ollama ollama pull <model:tag>`. Test locally before changing clients. This command is an example, not an instruction to pull unbounded models. Record license, language quality, JSON behavior, memory, output speed, and rollback model ID.

## Update workflow

1. Capture current config, image digest, model ID, and benchmark baseline.
2. Back up persistent data and secrets to owner-approved encrypted storage.
3. Choose a version deliberately; pull it, update the compose digest, validate config, and recreate.
4. Check health, JSON generation, latency, memory and logs.
5. If regression occurs, restore the previous compose digest/config and recreate. Runtime downgrade compatibility with stored models must be tested.
6. Refresh documentation/config snapshots and project integration notes.

No auto-upgrade of the inference container is configured. Unattended-upgrades being enabled does not prove all patches are current. Review host updates and reboot requirements separately. No reboot was performed to test persistence.

## Backup / restore

Important state: `/opt/narimato-ai/`, `/etc/caddy/`, `/var/lib/caddy/` (certificates/ACME state), Docker volume `narimato-ai_ollama`, SSH authorized_keys and relevant firewall configuration. Backups contain secrets; encrypt them and store separately from the server. Stop or otherwise quiesce services when consistency requires it.

Model weights can be downloaded again, but retain model manifests/digests for reproducibility. Do not copy a live Docker volume blindly as proof of a consistent backup. Provider snapshots are separate from application backups. An off-server backup and restore drill have not been implemented for this host (the owner accepted that for now; the Paperclip host has its own, documented in `paperclip/README.md`).

Recover on a compatible ARM64 Ubuntu host: install Docker/Compose and Caddy, restore configs/secrets with ownership/modes, restore model volume or repull recorded model, start Compose, validate Caddy, set firewall, update DNS if needed, issue/restore HTTPS certificates, then run health and task benchmarks. Verify each tenant's key (classscout, habigoal, camera, pandora, paperclip) and rejection of missing/invalid keys before reopening traffic.

## Troubleshooting

- SSH denied: unlock the correct key; check public fingerprint and authorized_keys through the provider console. Do not weaken host verification.
- DNS failure: query both authoritative nameservers; check A record and caches. `curl --resolve chatbotapi.haho.ai:443:2.31.100.246 ...` is diagnostic and does not prove DNS works.
- 401: verify the intended project's LOCAL_AI_API_KEY without displaying it. `/v1` alone is not an allowed route.
- Empty final content: send reasoning_effort none; avoid a tiny cap consumed by reasoning.
- Slow or failed generation: inspect queue, memory, CPU and timeout. Reduce prompt/output and concurrency. Do not repeatedly retry a saturated service.
- TLS error: inspect Caddy logs, DNS, TCP 80/443 reachability, certificate renewal and system time.

SSH accepts only the recorded key and fail2ban is active (see [ACCESS.md](ACCESS.md#key-only-ssh-and-fail2ban-owner-decision-2026-10-30)), but port 22 is still open to any address and the key may log in as root (`PermitRootLogin prohibit-password`). There are no per-key quotas or rate limits, and this host has no off-host backup or restore drill (the owner accepted this for now). These are recorded limits, not hidden guarantees; see [IMPROVEMENTS.md](IMPROVEMENTS.md).

## Context and cache limits

Ollama's global default remains 2048. Verified default Granite text profiles for Paperclip, ClassScout, Habigoal and Pandora use 8192 explicitly and cannot be selected by arbitrary client context fields. Keep `LLAMA_ARG_CACHE_RAM=128` and `LLAMA_ARG_CTX_CHECKPOINTS=2` in Compose; default 8-GiB caching caused repeated-request OOM kills under our 2800-MiB container cap even when one long request succeeded. The original pre-cache Compose snapshot is `/opt/narimato-ai/compose.before-context-cache.yaml`; restoring it can reintroduce that failure. Do not raise context merely by changing the global environment.

The gateway now runs `/opt/narimato-gateway-venv/bin/python`, a Python venv created with `--system-site-packages` to retain apt-installed Pillow, plus pinned `tokenizers==0.22.1` from gateway/requirements.txt. Its verified tokenizer is `/opt/narimato-gateway/tokenizers/granite4-h-1b.json`, SHA-256 `e2bad66439538cb4d5a7580680932432ed9ece9d3b8577e675512bdf11599253`; download source: https://huggingface.co/ibm-granite/granite-4.0-h-1b/resolve/main/tokenizer.json. Tokenizer hash mismatch rejects input. Include this artifact and dependency setup in recovery. The context deployment backup is under `/opt/narimato-ai/context-backup-*`, with prior service/config and private credentials.

Pandora now also runs in the tokenizers-enabled gateway venv, with MemoryMax=192M. Keep chat/context.py alongside its server. Its service uses root-only existing environment credentials and the same password hash. The chatbot context deployment backup includes gateway code/policy, Pandora code/UI and its prior unit. No credential rotation was performed.

## Fixed in the repository, not deployed yet

The defects of the [2026-10-30 review](GAP-ANALYSIS-2026-10-30.md#defects-found-while-checking) that could be corrected in code were corrected in the repository on 2026-10-31 and tested there. **The hosts still run the previous files**; nothing below has been copied or restarted. The fixes are independent unless a row says otherwise. A gateway restart drops queued and retained jobs (the gateway keeps them in memory only), so restart it when the queue is idle.

| Host | Copy | Then | Effect |
| --- | --- | --- | --- |
| Inference (2.31.100.246) | `gateway/server.py`, `gateway/metrics.py` | restart the gateway | `GET /v1/queue` reports the caller's own `per_service_limit` and `active_timeout_seconds`; the monitor and watchdog polls stop filling the metrics cap |
| | `operations/monitor.py` | restart the monitor | Stuck alert uses the job's timeout plus 120 s (at least 300 s); it needs the new gateway to see the timeout and otherwise keeps 300 s |
| | `storage/cleaner.py`, `config/model-storage-policy.json` to `/opt/narimato-ai/` | none; next hourly run | Cleanup reports older than 30 days are pruned |
| | `chat/server.py` | restart `narimato-chat` | Body check equals Caddy's 128,000 bytes |
| | `research/collect.py` and `config/tested-models.json` to `/opt/narimato-discovery/` (as `collect.py`, `tested-models.json`) | none; next daily run | Redirect targets are checked against the host allowlist; the model index lists all ranked tasks |
| Paperclip (2.29.113.132) | `paperclip/factory/search_workflow.py`, `paperclip/factory/business_metrics.py` to `/opt/narimato-factory` | restart `narimato-factory` | Discovery backlog counts every active task; the billing line shows the metered lane |
| | `paperclip/factory/provision.py` (with the factory code), `paperclip/configure-slg.py`, `paperclip/restore-drill.py`, `paperclip/snapshot.sh` to `/opt/narimato-paperclip` | none | A re-run keeps `remote_llm` and other settings; SLG setup leaves paused triggers paused; the recovery bundle includes the Segmind env file; the restore drill measures its three assertions. The next restore drill is the real test of the new measurements |

`paperclip/factory/factory.json` and `paperclip/local-ai.json` are snapshots of the live files; the live `factory.json` still holds eight unused keys, which can be removed at any convenient time.

## Known limitations

Behaviour of the current code, scripts and configuration that is recorded here and not changed. The review's remaining open decisions are listed in the [gap analysis](GAP-ANALYSIS-2026-10-30.md#defects-found-while-checking); the Paperclip-host ones are in [../paperclip/README.md](../paperclip/README.md#known-limitations).

- **Deploy helpers are single use, and nothing installs several units.** `scripts/deploy_gateway_update.py` is retired and refuses to run without an explicit flag. The other `deploy_*.py` helpers check the hash or baseline of the live source from when they were written (line 9 of each of `scripts/deploy_context_update.py`, `scripts/deploy_chatbot_context.py` and `scripts/deploy_observability.py`) and cannot be re-run unchanged. No tracked script installs `storage/cleaner.py`, `research/collect.py`, `operations/*` or their units and timers.
- **A long conversation can be refused before trimming.** Caddy limits `/chat` bodies to 128KB (`config/Caddyfile.example`) and the chat server applies the same limit. The page allows 30 earlier messages of up to 24,000 characters each, so a very long conversation can be refused with a 413 before the server's token-budget trimming runs.
