# Setup history — 2026-10-26 (Europe/Budapest)

## Decisions and actions

1. Goal: self-host a small LLM API for Habigoal and ClassScout.
2. Selected Hetzner CAX11, 2 ARM64 shared vCPUs, 4 GB RAM, 40 GB disk, Falkenstein. CAX21/8 GB was suggested for headroom; owner explicitly chose 4 GB for now.
3. Selected Apps -> Docker CE; Hetzner's documented base was Ubuntu 24.04, Docker and Compose preinstalled. Observed Docker 27.5.1 and Compose v2.32.4.
4. Owner generated an Ed25519 key named hetzner_ai and added the public key in Hetzner. Mac IPv6 test using `curl -6 --connect-timeout 10 https://api64.ipify.org` succeeded. Its address is not a fixed allowlist value.
5. Added IPv4 as well as IPv6 because outbound IPv6 from the actual Vercel deployments was not established. IPv4 was a compatibility choice, not proof that Vercel never supports IPv6.
6. Owner created narimato-chatbot at 2.31.100.246. A selected SSH key was visible. No additional volume was needed. Backups were suggested off for initial tests; current provider backup/firewall state was not independently verified via Hetzner's API.
7. Terminal execution initially failed due to local defaults. Using `/bin/sh`, login disabled, cwd `/` restored Mac terminal access. No app terminal was attached; SSH was launched as a fresh local command.
8. SSH public key was accepted but signing needed unlocking. Owner ran `ssh-add --apple-use-keychain ~/.ssh/hetzner_ai`; connection then worked.
9. Inspected memory, disk, listeners, Docker, Compose and running containers. Available memory was about 3.4 GiB, no swap, about 34 GB free before install; ARM64 confirmed.
10. Created /opt/narimato-ai; pulled Ollama image; pinned the downloaded image digest in compose.yaml. Configured loopback port, memory/CPU caps, sequential requests, bounded queue, persistent model volume and rotated container logs.
11. Downloaded qwen3:1.7b and ran native and OpenAI-compatible tests. Installed Caddy from Ubuntu's apt repository. System unattended-upgrades was observed enabled; actual recent patch status was not audited.
12. Enabled UFW allowing TCP 22, 80, 443 for IPv4 and IPv6. Existing SSH continued to work. Docker service itself remains loopback-only; do not assume UFW alone protects future Docker-published public ports.
13. Generated independent random project bearer keys and configured Caddy to permit only models and chat routes with either key. An initial header matcher failed validation; replaced it with a validated expression matcher before reloading. Sanitized current template is in config/.
14. Owner chose chatbotapi.haho.ai and manually created its GoDaddy A record. Observed nameservers ns21.domaincontrol.com / ns22.domaincontrol.com. Early results differed across nameservers/caches. A trusted certificate was issued; direct-IP SNI override tests worked while some name lookups still failed. Later standard hostname tests succeeded.
15. Verified both keys returned HTTP 200 for model inventory, missing auth returned 401, and public authenticated chat returned READY.
16. Created this local operations folder. Copied secrets to restricted private storage without printing them; SSH private identity remains in ~/.ssh.
17. Added only LOCAL_AI_API_KEY with the ClassScout-specific value to its existing ignored .env.local; verified it untracked and file mode 600. Vercel Production was not changed.

## Historical commands

The deployed configuration files capture the current runtime. These were the principal setup commands; do not run them blindly on an already configured server:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/hetzner_ai -C hetzner-ai
cat ~/.ssh/hetzner_ai.pub
ssh-add --apple-use-keychain ~/.ssh/hetzner_ai
ssh -i ~/.ssh/hetzner_ai root@2.31.100.246
mkdir -p /opt/narimato-ai
chmod 700 /opt/narimato-ai
docker pull ollama/ollama:latest
cd /opt/narimato-ai
docker compose up -d
docker exec narimato-ollama ollama pull qwen3:1.7b
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq caddy
ufw allow 22/tcp
ufw --force enable
ufw allow 80/tcp
ufw allow 443/tcp
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
systemctl enable caddy
```

The image initially used latest only to obtain an actual digest. The saved deployment uses that digest, not a floating latest tag. Keys and Caddy config were written programmatically; no secret values belong in command history. Do not recreate or overwrite the SSH identity.

## Sources checked during setup

- https://docs.hetzner.com/cloud/apps/list/docker-ce/
- https://docs.docker.com/engine/install/ubuntu/
- https://github.com/ollama/ollama/blob/main/docs/docker.mdx
- https://github.com/ollama/ollama/blob/main/docs/faq.mdx
- https://ollama.com/library/qwen3:1.7b
- https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx
- https://vercel.com/kb/guide/how-to-allowlist-deployment-ip-address

This is a reconstructed operational history with observed results, not a verbatim terminal transcript. No exact billing total is asserted: screenshots showed EUR 5.99/month before VAT for the plan before later IPv4 selection; verify actual invoice and add-ons in Hetzner.

## Personal chat addition

Added Pandora at /chat/ with the prototype site’s password-only Open flow, at the owner’s request. Dedicated loopback Python service and session cookie protect chat; no project bearer key is embedded in browser code. See CHAT.md for service and validation details.

## Capability benchmark

At the owner’s request, downloaded and evaluated qwen3:0.6b, qwen2.5:1.5b, gemma3:1b, llama3.2:1b, smollm2:1.7b and moondream:1.8b alongside qwen3:1.7b. Kept the existing CPU/memory/context limits, used read-only Atlas access and a single cached attributed OSM lookup, tested one public photo, and restored the original model. Candidate weights remain on disk. See ../benchmarks/capabilities/REPORT.md for full measured outcomes and limits. No production application configuration was changed.

## Separate image analytics and chat evaluation — completed 2026-10-27 Europe/Budapest

At the owner’s clarification, evaluated image analytics independently of chat. Attempted two Gemma 4 E2B packages, then tested and tuned alternative vision candidates within the existing memory cap. SmolVLM2 and Granite Vision completed the image/JSON checks. Ran separate Granite/EuroLLM/Qwen text and language tests and a text-only Ministral attempt. Preserved raw failures, cgroup evidence, settings, scripts, and findings in ../benchmarks/round2/. Failed Gemma weights were removed after metadata preservation; other model weights remain. The original model was restored; public project authentication and services were checked. No image endpoint or production application model change was deployed.

## Language workstream separation

At the owner’s instruction, separated non-English capability management entirely from English chat, structured-task and image recommendations. Preserved original observations and mixed historical runners; created independent English results and Hungarian evidence, a dedicated non-English runner, per-language acceptance guidance and updated agent instructions. No new inference run or production routing/model change was performed for this documentation/scoring correction.

## Additional candidate tests — 2026-10-27

Tested five additional English text variants and six additional image variants sequentially with the same server memory cap and no non-English tests. Downloaded candidate weights were removed after recording resolved metadata and results; original packages were preserved. Ran one separate larger-budget English check for each of two always-thinking candidates. Updated independent English/image rankings and the Round3 report. No model, public endpoint, application environment or routing selection was deployed.

## 2026-10-27: Camera review-assistance API

After independent nine-category testing, the owner accepted imperfect screening as human-review assistance. Added a dedicated LFM2.5-VL 450M worker on loopback 8089, exposed through authenticated `/v1/moderation/*` routes. Dedicated Camera credential stored in protected server/local files; existing project keys preserved. Asynchronous bounded in-memory jobs, input validation/resizing, explicit review-only results, nullable categories, failure states, idempotency and short retention were implemented. No image URL fetching or arbitrary prompt/model selection is exposed.

Installed distribution `python3-pil` (Pillow 10.2.0 at deployment), native systemd worker with 384 MiB cap, and persisted the tested 450M model package. Caddy candidate validation passed before reload; other routes retain their 128 KB limit, moderation requests have a separate 6 MB proxy limit. Source and protected config snapshots refreshed. Unit and public HTTPS end-to-end checks recorded under `results/moderation-api/`; no Camera repository/Vercel integration was deployed. See `docs/CAMERA-MODERATION.md` for contract, examples, credentials, limits, failure handling and operations.

## 2026-10-27: Shared text/image job routing

Added a central authenticated FIFO scheduler for text_chat, image_moderation and image_recognition. Existing ClassScout/Habigoal chat requests and Camera moderation aliases now use it; Pandora's backend also moved to the same gateway. Service permissions and per-tenant job retrieval are enforced; no arbitrary model pull/selection is exposed. Queue bounds, expiry, result retention, idempotency and an upstream-uncertain circuit are explicit. One worker controls unloading/model changes before inference. No runtime CPU/RAM limits were raised.

Cutover used temporary maintenance, private backups, stopped direct-call services, drained models, validated Caddy, enabled narimato-gateway and disabled the legacy moderation worker. Mixed HTTPS testing completed text → moderation → recognition → text without overlap and observed two model switches; compatibility, isolation, JSON text and buffered SSE were verified. Existing Camera aliases and both project authentication checks passed. Twelve unit tests cover serialization, permission boundaries, expiry, capacity, idempotency, model switching, circuit failure, inputs and moderation semantics. No Camera/ClassScout application integration was changed; ClassScout's existing short timeout remains a documented application constraint. See docs/JOB-ROUTER.md and results/gateway/.

## 2026-10-27: Correct text model assignment

The shared queue initially preserved the previously deployed Qwen3 text route, despite Granite 4 1B Hybrid leading the English structured-task benchmark. After the owner questioned the Qwen identity reply, changed text_chat to granite4:1b-h for ClassScout, Habigoal and Pandora; the installed package ID is 7761ae79cab9. Camera's agreed LFM2.5-VL 450M assignments are unchanged. Existing qwen3:1.7b client input is an explicit legacy alias rewritten to Granite so existing ClassScout calls remain compatible; actual response metadata reports Granite. Pandora uses model auto, with a clearer persona instruction. Queue drained before the controlled update; no in-flight work was intentionally discarded. Earlier benchmark reports remain historical evidence rather than current configuration.

## 2026-10-27: Ranking-driven defaults and explicit alternatives

Owner directed defaults to follow the best task-specific ranking after every test round, with alternative installed models exposed to clients. Added a deterministic generated policy sourced from separate English, general-image and moderation evidence, with source hashes, exact tested artifact digests and per-task profiles. Gateway auto selection hot-loads the policy; installed discovery is intersected with task evidence and tenant permissions. Unknown, missing or changed artifacts are blocked instead of pulled or silently substituted. Concrete IDs now select the actual model; the temporary Qwen-to-Granite alias was removed.

General recognition now defaults to the first general-image table entry, LFM2-VL 450M Q8; its exact previously tested package was installed and verified. English remains Granite 4 1B Hybrid; moderation remains LFM2.5-VL 450M under its own ranking. ClassScout's ignored local env now sets LOCAL_AI_MODEL=auto; no tracked ClassScout files or Vercel Production variables changed. Required future test completion steps are in AGENTS.md and docs/MODEL-POLICY.md. Live verification listed 18 installed artifacts, ten text-selectable and six Camera-selectable, and exercised auto text, explicit Qwen 0.6B/1.7B, auto recognition, explicit LFM2.5 recognition and auto moderation through the shared queue.

## 2026-10-27: Continuous discovery, backlog and retention

Owner requested periodic discovery, a testing backlog and storage/training rules, then explicitly confirmed approved curated datasets/labels only and no live Camera/conversation capture for training. Added a daily server systemd metadata collector at 03:30 Europe/Budapest plus up to 15 minutes jitter; first run succeeded across 12 feeds. It stores bounded public metadata/shortlists, not model weights or customer requests. Scope filtering excludes speech/embedding/time-series-only models. A 28-variant tested index and decline records preserve evidence and prevent unchanged repeat tests.

Added the research/testing backlog, independent evaluation gates, future review cadence, metadata-only storage targets and approved dataset manifest example. Removed the two explicitly declined current-environment packages (Qwen3-VL 2B and Ministral 3B) with artifact/evidence audit; no default, active or pinned model was removed. Free disk increased to about 11 GiB. The shared gateway now expires terminal result records after five minutes, clears last-worker references, and provides owner-scoped DELETE acknowledgement/queued cancellation; active inference cannot be unsafely cancelled. No live payload archive, training capture, actual training run, unattended benchmark job or external notification was enabled.

## 2026-10-27: Automatic top-five/recent-demand model cleanup

Owner requested retaining only top-ranked candidates plus models with valid requests in the last two weeks, excluding tests. Implemented top five per job-specific ranking and a 14-day admitted-production-demand window; this replaces static pins/rollback-cache targets. Added content-free durable usage metadata and explicit test markers across verification/benchmark tools. Existing inventory gets one initial 14-day history grace because earlier non-test usage cannot be reconstructed. No model content, prompt, answer, image, result evidence, user ID or tenant ID enters the usage ledger.

An hourly systemd cleaner uses an independent loopback-only maintenance key and gateway lease: it skips busy queues, prevents admission while removing weights, rechecks rank/usage/digest/residency, and records identity/digest before deletion. The lease has a deadline and the operation has a shorter timeout. Validation begun before a cleanup epoch cannot admit stale work afterward; releasing the lease invalidates discovery cache. The first run removed a newly created disposable alias while keeping the source and all protected models. Tests confirmed marked requests do not update production demand, service keys cannot manage cleanup, and active/queued work blocks deletion. All benchmark/decline metadata and approved datasets remain untouched.

## 2026-10-28: broader public-research Camera evaluation

Five working vision artifacts completed separate recognition (32 photographs) and moderation (41 cases) cohorts, with paired robustness and separate count probes. There are 70 distinct primary images across the overlapping cohorts. Public references, frozen label/scorer revisions, exact artifacts, invalid outputs, category misses, baselines, uncertainty and resource evidence are published in [the full report](../benchmarks/vision-evaluation/REPORT.md). No live Camera inputs or training use.

MiniCPM-V 4.6 1B is the recognition default. Qwen3.5 0.8B narrowly ranks first for moderation and uses explicit think=false; English text stays Granite 4 1B Hybrid. The narrow image/moderation comparisons do not establish general superiority or production safety. All 38 final API checks passed, default digests match, both timers/services are healthy, Granite was restored resident, and dedicated temporary server image folders were removed. Free disk was 7.249 GiB; protected weights remain under the top-five/14-day policy.

## 2026-10-29: Round 6 and repository catch-up

The 8K text-context state that had run in production since 2026-10-27 was committed (it had never been in git). Round 6 then evaluated LFM2 1.2B, OLMo 2 1B, SmolVLM2 256M and InternVL3.5 1B: no ranking leader changed, 52 variants are now indexed, and InternVL3.5 1B is recorded as incomplete because of a runner fault rather than as a quality failure. The regenerated policy and refreshed public dashboard were then deployed with the owner's approval and verified through the public API (11/11 checks). See [the Round 6 report](../benchmarks/round6/REPORT.md).
