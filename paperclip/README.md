# Narimato Paperclip

Prepared 2026-10-27, Europe/Budapest.

Open https://paperclip.haho.ai and enter the same secret as Pandora, then press **Open**. No username or second Paperclip login. The initial company is **Narimato**. A local Granite 4 1B Hybrid inference connection is prepared with an 8K total context window. The [source-page factory](factory/README.md) provides Research Analyst, Content Quality Reviewer and Support Drafter agents plus a [human-approved publication workflow](factory/PUBLISHING.md) for complete ClassScout class listings; no cloud subscription is required for this selected model. Claude and Codex CLIs, Python and Git are already installed in the official image. The existing ClassScout intake credential is connected through a separate root-only service file. No paid model run has been started.

## Local model decision

[Model selection and implementation boundary](MODEL-SELECTION.md): Granite 4 1B Hybrid on the existing chatbot server is selected for a bounded English research/support pilot. The dedicated credential and tested 8K inference profile are provisioned. The source-page worker, budgeted Brave discovery and five native operating workflows are deployed. Eligible ClassScout new Classes listings and scoped contact/content updates use an automatic quality gate; unsupported cases remain held. See [the current policy and measured limits](factory/WORKFLOWS.md#evidence-branches-formats-dashboard-and-padel-africa--v4). Customer replies remain drafts.

## Active local inference profile

Paperclip has its own `paperclip` tenant at `https://chatbotapi.haho.ai/v1`. Use `model: auto` and the shared async `POST /v1/jobs` route for long inputs; the selected Granite model has an 8192-token total window, up to 1024 output tokens, exact tokenizer-based admission with 1536 tokens conservatively reserved for template overhead, and one pending Paperclip job. Inputs above 4096 counted tokens must use async jobs. Default ClassScout, Habigoal and Pandora Granite text now also use verified 8192-token profiles. Explicit alternative models retain their tested limits. A future winning model without verified Paperclip context evidence fails explicitly until tested.

Connection metadata is `/opt/narimato-paperclip/local-ai.json`; its independent key is in root-only `/etc/paperclip-local-ai.env`. Local metadata copy: local-ai.json. The credential is used by the server-side factory worker; it is not embedded in the UI or agent prompts. Do not use another project's key. Normal workers should poll results and delete them after use; results expire five minutes after completion. The shared CPU queue means long research can delay other jobs; this is not dedicated throughput.

The 8K native long test processed 6892 input tokens in 143.260 seconds. A bounded prompt cache (128 MiB) and two checkpoints prevented the repeated-request memory failure seen with default caching. All fourteen existing English structured checks plus native tools passed afterward, without a new OOM kill. Long-run peak anonymous memory was about 1947 MiB, with minimum host available memory about 1390 MiB. These are bounded test measurements, not a load or autonomy certification. See [full evidence](../benchmarks/paperclip-context/README.md).

## Deployment

- Hetzner host `narimato-paperclip`, IPv4 `2.29.113.132`; supplied IPv6 allocation `2a01:4f9:c01d:3025::/64` (no AAAA record provisioned).
- Ubuntu 26.04 LTS, x86_64, approximately 4 GB RAM / 40 GB disk, 2 GB swap added.
- GoDaddy A record `paperclip` → `2.29.113.132`, TTL 600. Authoritative and public resolver checks passed.
- Caddy handles HTTPS with automatic Let's Encrypt renewal and HTTP-to-HTTPS redirection.
- Official Paperclip `2026.1023.0`, source revision `1b4c803816e82b0265c8422e1a804327a7ed8c54`. Immutable image digest recorded in image-metadata.json and server `.env`; no automatic image updates.
- Docker Compose root `/opt/narimato-paperclip`; container `narimato-paperclip`, restart `unless-stopped`, memory ceiling 2800 MiB, 2 CPUs, capped logs.
- Host network is intentional: Paperclip `local_trusted` requires binding to loopback. Paperclip listens only at `127.0.0.1:3100`; PostgreSQL listens only on loopback port 54329. Browser authentication is enforced by Caddy's forward-auth gate before every UI, API and WebSocket request. This is a single-owner shared-password deployment, with Paperclip's local board identity behind the external gate.
- Gate at `127.0.0.1:8088`, systemd `paperclip-access`. Password SHA-256 hash copied securely from Pandora; independent persistent HMAC session-signing key. Secure, HttpOnly, SameSite Strict host-only cookie, 30-day expiry. Login attempts are bounded per IP; unsafe requests require the exact public Origin.
- UFW permits only SSH, HTTP and HTTPS, on both IP families. Docker and Caddy start at boot.

The two servers have independent passwords hashes after provisioning: later Pandora password rotation does not automatically rotate Paperclip. Read the new hash programmatically and update `/etc/paperclip-access.env` when authorized. Keep the signing key unchanged unless deliberately invalidating existing sessions. Never print either environment file or paste a password into shared documentation.

## Persistent data and recovery

`/opt/narimato-paperclip/data` contains embedded PostgreSQL, uploaded files, workspaces and the encryption master key. The root-only Compose `.env` contains persistent authentication/tool-action/agent-JWT signing secrets. `/etc/paperclip-access.env` is root-only and read by systemd.

Paperclip's built-in database backups run hourly and retain seven days. An initial manual SQL backup succeeded, and the health endpoint reports the backup. `snapshot.sh`, installed at `/opt/narimato-paperclip/snapshot.sh`, takes another SQL backup and writes a mode-600 recovery archive under `/root/paperclip-backups/`, including persistent non-database files and deployment/signing secrets. The live database directory is excluded in favor of SQL dumps. With the factory installed, it also includes its worker/configuration, service unit, restricted ClassScout connection environment and a consistent SQLite backup including publication approvals/receipts. Run it before upgrades. Archives are sensitive. This helper does not prune full archives.

A verified initial recovery archive is stored outside the server at ignored `private/paperclip/initial-recovery.tar.gz`, mode 600. This is a one-time copy, not recurring off-site protection. A separate factory recovery copy is saved after the source-page acceptance pilot. Refresh recovery copies after provider connection or important configuration changes. An isolated PostgreSQL 18.1 restore using the official restore function passed on 28 October, recovering one company, five agents and 32 issues from the 02:11 UTC backup. The temporary cluster was stopped and removed. A full replacement-host recovery including files, credentials and app startup remains untested.

For recovery on a replacement server: install Docker/Compose, Caddy, Python aiohttp and UFW; restore the archived deployment/secrets/persistent files with their restrictive modes; start the pinned container and allow it to initialize the database; restore the chosen SQL dump into an empty database using the matching embedded PostgreSQL tools; restart Paperclip, validate/reload Caddy and rerun access checks. Do not overwrite a live production database with an unreviewed restore. For the factory, restore its SQLite snapshot into `/var/lib/narimato-factory/factory.sqlite3`, preserve restrictive ownership for the service StateDirectory, and enable `narimato-factory.service`. Recheck source-page tasks before normal use. Keep the encryption master and signing keys paired with the restored database.

## Operations

Connect with the existing owner key (never copy it into this repo):

```sh
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.29.113.132
cd /opt/narimato-paperclip
docker compose ps
docker compose logs --tail 40
systemctl status paperclip-access caddy --no-pager
```

The host ED25519 key was accepted on first use and saved in the owner's known-hosts file; it was not independently compared with the Hetzner console. Never ignore a changed-host warning.

Validate Compose with `docker compose config --quiet`; the non-quiet form expands secrets. Validate Caddy before reload. Preserve the mounted data and existing `.env` for restart or upgrade. Never use `docker compose down -v` as maintenance.

Public remote agent API calls also require the password gate; external agents/webhooks need a separately designed authentication path. Local agents use loopback directly. Do not create an unauthenticated proxy exception for all `/api` routes.

## Verification

`python3 paperclip/verify.py` reads the Pandora secret from ignored private storage without printing it. It verifies HTTPS, login, wrong-password and spoofed-header refusal, app health, company access, cookie attributes, origin enforcement, real WebSocket connection/refusal, logout cookie clearing and tamper refusal. See verification.json. No full browser visual test or paid provider inference was performed. Company persistence was confirmed after container recreation. Application health is checked by Docker.

Upstream references: https://github.com/paperclipai/paperclip/blob/master/doc/DOCKER.md and https://github.com/paperclipai/paperclip/blob/master/doc/DEPLOYMENT-MODES.md. The installed image is pinned; upstream master may have newer behavior.

OpenClaw alignment, the 18-routine portfolio, structured program gates and verified recovery are documented in [factory/WORKFLOWS.md](factory/WORKFLOWS.md#openclaw-alignment-and-recovery--v6-28-october-2026).

The company now includes a five-minute native coordination routine for durable handoffs and safe evidence recovery. Its scheduled acceptance and stopping rules are in [factory/WORKFLOWS.md](factory/WORKFLOWS.md#autonomous-coordination-system-improvement-28-october-2026).
