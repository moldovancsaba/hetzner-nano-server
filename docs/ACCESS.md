# Access and secrets

## SSH

Host: `2.31.100.246`; user: `root`; port: `22`. Identity: `/Users/chappie/.ssh/hetzner_ai`; public identity: same path with `.pub`.

Recorded client key fingerprint: `SHA256:DcTTtdUVM0pNAK6MKvQLZBBlEHflUs/F/lhBKgXJ6uk`.
Recorded server ED25519 fingerprint: `SHA256:8wu0a4hcJjhFtO2daQSxtSD6FrPHyjtoxU5+NJFkMkI`.

The initial connection used trust on first use (`StrictHostKeyChecking=accept-new`); the fingerprint was not independently checked in the Hetzner console. Future connections use the recorded known-host entry. Never suppress a changed-host warning; verify through Hetzner's console. Do not remove known-host records merely to make a connection succeed.

A locked key caused the first authentication attempt to fail despite the server accepting its public key. The owner unlocked it using `ssh-add --apple-use-keychain ~/.ssh/hetzner_ai`. If an agent cannot use the key, ask the owner to unlock it locally; do not request the passphrase in chat.

### Key-only SSH and fail2ban (owner decision 2026-10-30)

Both hosts (the AI host above and the Paperclip host `2.29.113.132`) accept only the recorded client key above for `root`. Password and keyboard-interactive login are off, `MaxAuthTries` is 3 and `LoginGraceTime` 30 s: [config/sshd-narimato-hardening.conf](../config/sshd-narimato-hardening.conf), installed as `/etc/ssh/sshd_config.d/10-narimato-hardening.conf` (sshd reads the drop-in directory first and the first value wins). fail2ban runs on both with an `sshd` jail in aggressive mode: five failures in ten minutes ban the address for an hour, and the two hosts never ban each other ([config/fail2ban-narimato.local](../config/fail2ban-narimato.local) as `/etc/fail2ban/jail.d/narimato.local`). The operator's current address is also added to `ignoreip` on the hosts only, so a mistake cannot lock the operator out; the file in Git does not carry it.

Before the change the hosts saw roughly 7,800 (Paperclip) and 15,500 (AI) failed logins a day. After it a password attempt answers "Permission denied (publickey)". It was applied with an automatic revert armed (a transient timer that removes the drop-in after ten minutes), proved with a fresh key login and a refused password login on each host, then disarmed. If key access ever breaks, use the Hetzner console: the root account password is locked, so the console's rescue/reset flow is the way in, not a password. Lifting a ban: `fail2ban-client set sshd unbanip <address>`.

## API credentials

Canonical secret store: server `/opt/narimato-ai/api-keys.json`, mode 600, parent mode 700. Local restricted copy: `../private/api-keys.json`, mode 600, private directory mode 700. Keys were generated with Python `secrets.token_urlsafe(36)`, separately for `habigoal` and `classscout`. The `camera`, `pandora` and `paperclip` tenants have their own independent keys in the same file.

Actual keys are in the private file, not this document. Read them programmatically for the intended project. Never print the complete secret to verify it. `scripts/healthcheck.py` reads it without displaying it.

Caddy's live configuration, `/etc/caddy/Caddyfile`, holds no bearer keys: it only terminates HTTPS, routes and limits request size, and the gateway authenticates every key from `/etc/narimato-gateway.env`. `/opt/narimato-ai/Caddyfile` and the dated `*.before-*` backups beside it are older snapshots; the backups may still contain keys, so keep them root-only (600). Local copy of the live file: `private/Caddyfile.live` (600), refreshed 2026-10-29. Do not enable debug output that dumps adapted configuration.

Separate keys support independent revocation, per-tenant queue limits (four queued plus running jobs each; one for Paperclip) and per-tenant job-type permissions (see [the job router](JOB-ROUTER.md)). They do NOT provide quotas, request rate limits or protection against repeated bad-key attempts.

## Local application handoff

ClassScout: `/Users/Shared/Projects/classscout/.env.local`, `LOCAL_AI_API_KEY` has been set and verified ignored/untracked. Restart or reload its process to pick it up. No unrelated environment variables were replaced. The integration agent must verify its own base URL/model environment and runtime configuration.

Habigoal key is prepared but this setup did not write its application environment. Vercel Production keys were not configured. Configure only the intended server-side environment when authorized; never use `NEXT_PUBLIC_*` for a secret.

## Account access

No Hetzner API token, GoDaddy account credential, or SSH passphrase is stored here. DNS was changed manually by the owner. No automated account access should be inferred from SSH access.

## Rotation

Bearer keys are checked by the gateway, not Caddy, and it accepts exactly one key per tenant, so there is no overlap period. To rotate one tenant: generate the new key on the server; update that tenant's entry in the canonical `/opt/narimato-ai/api-keys.json` and its `GATEWAY_<TENANT>_KEY` line in `/etc/narimato-gateway.env`; update the consuming application's server-side secret (for Pandora, `GATEWAY_PANDORA_KEY` in `/etc/narimato-chat.env`); then drain the queue and restart `narimato-gateway` (restarting loses in-memory jobs). The old key stops working at that restart, so change the consumer immediately before or after it and verify successful calls and a rejected old key. Refresh the restricted local snapshot. The maintenance key (`GATEWAY_MAINTENANCE_KEY` in `/etc/narimato-model-cleanup.env`, read by the gateway and the cleaner) is rotated separately in that file. Nothing automates this procedure; preserve rollback copies securely. Do not revoke several tenants' keys together unless required.

## Camera moderation credential

The dedicated `camera` key in the canonical/local key JSON authenticates Camera jobs at the shared gateway (`GATEWAY_CAMERA_KEY` in root-only `/etc/narimato-gateway.env`). `/etc/narimato-moderation.env` belonged to the retired standalone worker. Local handoff: `private/camera-moderation.env` (600, ignored). It is not accepted by chat routes. See [Camera moderation](CAMERA-MODERATION.md) for use and rotation. Existing Habigoal/ClassScout keys and paths are preserved.

## Shared job router credentials

Active runtime keys are in `/etc/narimato-gateway.env` (600), separate `GATEWAY_CLASSSCOUT_KEY`, `GATEWAY_HABIGOAL_KEY`, `GATEWAY_CAMERA_KEY` and internal `GATEWAY_PANDORA_KEY`. Existing service keys are preserved; Pandora has a new dedicated backend-only key, also provisioned to its root-only chat env. The canonical/local key JSON now includes `pandora`; do not expose it in browser code. Caddy no longer embeds active bearer keys, but older private backups do. Rotate the intended field in the canonical store, gateway env and authorized consumer env; drain/restart the gateway. For Pandora also refresh/restart its chat backend. Retired moderation env is no longer the active credential source.

## Paperclip local inference

The canonical key JSON includes independent `paperclip` credentials, also in `/etc/narimato-gateway.env` as `GATEWAY_PAPERCLIP_KEY`. Its only permitted job is text chat. The Paperclip host stores the key in root-only `/etc/paperclip-local-ai.env`; metadata is `/opt/narimato-paperclip/local-ai.json`. The UI does not receive the key. The source-page factory worker is deployed with research, quality review and support drafting roles. Rotate this tenant independently and update that root-only handoff, never reuse another project credential. The ignored local canonical snapshot has been refreshed.
