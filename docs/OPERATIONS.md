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

## Known limitations

Behavior of the current code, scripts and configuration that is recorded here and not changed. Line numbers match the files when this section was written; the named function or setting is the stable reference.

- **Queue report shows the wrong limit for Paperclip.** `Scheduler.status()` returns `per_service_limit: 4` for every key (`gateway/server.py`, line 371). Admission allows Paperclip one queued plus running job (`gateway/server.py`, line 310). A Paperclip client reads 4 from `GET /v1/queue` but is refused with 429 `busy` at 1.
- **Long 8K jobs can trip the stuck-inference alert.** The monitor raises critical `inference_stuck` when one job has been active for more than 300 seconds (`operations/monitor.py`, line 25). Text on the 8K profile may run for up to 900 seconds (`timeout_seconds` in `config/runtime-context-profiles.json`, used at the native call in `Runner.__call__`).
- **Watchdog polls use most of the metrics event cap.** The monitor (`operations/monitor.py`, line 141) and the external watchdog (`operations/external_watchdog.py`, line 35) each request `/v1/queue` about every 30 seconds, and each request is stored as an `http` event (`gateway/server.py`, lines 464-467). That is about 2,880 events a day each, about 172,800 over the 30-day retention, against a cap of 200,000 (`gateway/metrics.py`, lines 15-16). About 27,000 events per 30 days remain for real traffic; beyond that the oldest events are discarded early and `full_window_tracked` reports false. The polls are marked as tests, so production counts are unaffected.
- **Cleaner reports are never pruned.** Line 43 of `storage/cleaner.py` writes a new `cleanup-<UTC>.json` on every run, hourly, plus a copy of the latest report. Nothing deletes old ones, so about 24 small files a day accumulate in `/var/lib/narimato-model-cleanup/`.
- **`scripts/deploy_gateway_update.py` does not ship every module the gateway imports.** It copies five files (`FILES`, `scripts/deploy_gateway_update.py`, line 8). `gateway/server.py` also imports `gateway/usage.py`, `gateway/metrics.py`, `gateway/hungarian.py` and `gateway/long_context.py` (`gateway/server.py`, lines 22-26), which it leaves as they are. The other `deploy_*.py` helpers check the hash or baseline of the live source from when they were written (line 9 of each of `scripts/deploy_context_update.py`, `scripts/deploy_chatbot_context.py` and `scripts/deploy_observability.py`) and cannot be re-run unchanged. No tracked script installs `storage/cleaner.py`, `research/collect.py`, `operations/*` or their units and timers.
- **`scripts/verify_gateway.py` no longer matches the deployment.** Line 21 of `scripts/verify_gateway.py` expects ClassScout and Habigoal to see only `text_chat` in `/v1/job-types`; they also have `text_chat_hu`, so the assertion fails. line 38 expects image defaults that are no longer the ranked defaults.
- **`tests/test_gateway.py` embeds environment and default assumptions.** Line 89 of `tests/test_gateway.py` expects the text default to be `granite4:1b-h`; it passes now and needs editing whenever the ranked default changes. `test_http_permissions_async_chat_and_sse` (`tests/test_gateway.py`, line 93) submits a ClassScout text job, whose default profile is 8K, so it uses the real tokenizer (`gateway/long_context.py`, line 16) and needs the verified tokenizer file at `GRANITE_TOKENIZER_PATH` or the default path.
- **The discovery host allowlist is not applied to redirects.** `research/collect.py` (lines 61-63) checks the host of the requested URL only, and `urlopen` follows redirects without re-checking. The size and time limits still apply (`research/collect.py`, lines 63-65), and the collector downloads no weights and executes nothing.
- **Chat request size is set by Caddy, not by the chat server.** Caddy limits `/chat` bodies to 128KB (`config/Caddyfile.example`, line 26); the chat server's own 256 KiB check (`chat/server.py`, line 36) is never reached through the proxy. The page allows 30 earlier messages of up to 24,000 characters each, so a long conversation can be refused by Caddy with a 413 before the server's token-budget trimming runs.
- **`config/tested-models.json` lags the generated policy.** Rebuilding it with `scripts/build_tested_model_index.py` adds `ranked_tasks` to the two Round 6 text models (LFM2 1.2B, OLMo 2 1B) and SmolVLM2 256M. Nothing reads that field except the dashboard builder, which regenerates the index in memory, so the dashboard is unaffected.
