# Access and secrets

## SSH

Host: `2.31.100.246`; user: `root`; port: `22`. Identity: `/Users/chappie/.ssh/hetzner_ai`; public identity: same path with `.pub`.

Recorded client key fingerprint: `SHA256:DcTTtdUVM0pNAK6MKvQLZBBlEHflUs/F/lhBKgXJ6uk`.
Recorded server ED25519 fingerprint: `SHA256:8wu0a4hcJjhFtO2daQSxtSD6FrPHyjtoxU5+NJFkMkI`.

The initial connection used trust on first use (`StrictHostKeyChecking=accept-new`); the fingerprint was not independently checked in the Hetzner console. Future connections use the recorded known-host entry. Never suppress a changed-host warning; verify through Hetzner's console. Do not remove known-host records merely to make a connection succeed.

A locked key caused the first authentication attempt to fail despite the server accepting its public key. The owner unlocked it using `ssh-add --apple-use-keychain ~/.ssh/hetzner_ai`. If an agent cannot use the key, ask the owner to unlock it locally; do not request the passphrase in chat.

## API credentials

Canonical secret store: server `/opt/narimato-ai/api-keys.json`, mode 600, parent mode 700. Local restricted copy: `../private/api-keys.json`, mode 600, private directory mode 700. Keys were generated with Python `secrets.token_urlsafe(36)`, separately for `habigoal` and `classscout`.

Actual keys are in the private file, not this document. Read them programmatically for the intended project. Never print the complete secret to verify it. `scripts/healthcheck.py` reads it without displaying it.

Caddy's live config also holds both keys at `/etc/caddy/Caddyfile` (root:caddy, 640) and `/opt/narimato-ai/Caddyfile` (600). Local copy: `private/Caddyfile.live` (600). Treat all these as secrets. Caddy supports authentication here via a header expression; do not enable debug output that dumps its adapted configuration.

Separate keys support independent revocation; they do NOT provide different quotas, tenant isolation, project-level rate limits, or model permissions. Both keys can use the same allowed routes.

## Local application handoff

ClassScout: `/Users/Shared/Projects/classscout/.env.local`, `LOCAL_AI_API_KEY` has been set and verified ignored/untracked. Restart or reload its process to pick it up. No unrelated environment variables were replaced. The integration agent must verify its own base URL/model environment and runtime configuration.

Habigoal key is prepared but this setup did not write its application environment. Vercel Production keys were not configured. Configure only the intended server-side environment when authorized; never use `NEXT_PUBLIC_*` for a secret.

## Account access

No Hetzner API token, GoDaddy account credential, or SSH passphrase is stored here. DNS was changed manually by the owner. No automated account access should be inferred from SSH access.

## Rotation

Generate a new project key on the server, stage Caddy acceptance of both old and new values, validate/reload Caddy, update the application's server-side secret, verify successful calls, then remove old-key acceptance and validate/reload again. Update the canonical JSON and restricted local snapshot. The current config does not automate this procedure; preserve rollback copies securely. Do not revoke both projects' keys together unless required.

## Camera moderation credential

The dedicated `camera` key in the canonical/local key JSON authenticates only the moderation worker. Root-only runtime environment: `/etc/narimato-moderation.env`; local handoff: `private/camera-moderation.env` (600, ignored). It is not accepted by chat routes. See [Camera moderation](CAMERA-MODERATION.md) for use and rotation. Existing Habigoal/ClassScout keys and paths are preserved.
