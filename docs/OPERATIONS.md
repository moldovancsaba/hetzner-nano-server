# Operations and recovery

## Shared inference gateway

Text, Camera image jobs and Pandora now pass through `narimato-gateway`. See [job-router operations](JOB-ROUTER.md#operations-and-changing-assignments). The former standalone moderation service stays disabled. Drain queued work before maintenance; restart loses in-memory jobs. If the gateway opens its upstream-uncertain circuit, inspect/stop unfinished inference before restarting it. Direct native benchmark/generation calls bypass scheduling and should not run alongside production traffic.

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

Model weights can be downloaded again, but retain model manifests/digests for reproducibility. Do not copy a live Docker volume blindly as proof of a consistent backup. Provider snapshots are separate from application backups. An off-server backup and restore drill have not been implemented.

Recover on a compatible ARM64 Ubuntu host: install Docker/Compose and Caddy, restore configs/secrets with ownership/modes, restore model volume or repull recorded model, start Compose, validate Caddy, set firewall, update DNS if needed, issue/restore HTTPS certificates, then run health and task benchmarks. Verify both project keys and rejection of missing/invalid keys before reopening traffic.

## Troubleshooting

- SSH denied: unlock the correct key; check public fingerprint and authorized_keys through the provider console. Do not weaken host verification.
- DNS failure: query both authoritative nameservers; check A record and caches. `curl --resolve chatbotapi.haho.ai:443:2.31.100.246 ...` is diagnostic and does not prove DNS works.
- 401: verify the intended project's LOCAL_AI_API_KEY without displaying it. `/v1` alone is not an allowed route.
- Empty final content: send reasoning_effort none; avoid a tiny cap consumed by reasoning.
- Slow or failed generation: inspect queue, memory, CPU and timeout. Reduce prompt/output and concurrency. Do not repeatedly retry a saturated service.
- TLS error: inspect Caddy logs, DNS, TCP 80/443 reachability, certificate renewal and system time.

The host currently allows SSH from anywhere. Root SSH, public SSH scope, absence of per-key quotas, and backup/monitoring gaps are recorded improvement items, not hidden guarantees.
