# Improvements and outstanding verification

## First: connect applications and establish evidence

- Complete each project's backend integration; set only its own production secret when authorized. Verify a request originating in the actual Vercel function. Local success is not deployment verification.
- Build project-specific evaluation sets. Pick workflows based on demonstrated accuracy, not model marketing or parameter count.
- Add application request limits, prompt/output caps, timeouts, cancellation and graceful unavailable behavior. Disable uncontrolled retries.
- Collect latency, successful task counts, queue errors, memory peaks and failures without logging secrets or personal prompt content.

## Reliability and access

- Add an unprivileged operator account and least-privilege sudo; test it before changing root access.
- Consider limiting SSH source networks or a VPN; the owner's IPv6 address can change. Maintain console recovery access.
- Independently confirm SSH host fingerprint through Hetzner's console.
- Implement encrypted off-server backups and test restoration. Confirm provider backup settings and actual costs.
- Add certificate/service/disk alerts and periodic health checks only when the owner chooses a monitoring destination and schedule. No automation or notifications were created here.
- Review host patches, container versions, restart behavior after reboot, and ACME renewal. A configured restart policy is not a tested reboot recovery.
- Add per-project quotas and rate limiting if traffic grows. Current keys identify access but do not isolate workload or costs.
- Review security implications of host-published Docker ports; keep inference bound to loopback. Rotate keys with overlap and independent verification.

## Capacity and model quality

- Try a smaller model only if latency or concurrency is unacceptable; assess accuracy loss on the same data.
- Try 8 GB RAM / more CPU only after recording memory pressure, OOMs, latency and queue metrics. Extra RAM alone does not guarantee faster generation.
- Evaluate retrieval or deterministic code for facts and simple rules instead of asking a tiny model to invent answers.
- Keep short context by selecting relevant source text; no unlimited chat history. Test multilingual inputs used by both products.
- Consider GPU hosting only if measured throughput/quality needs justify its cost. No GPU is present on this plan.

## Deliberate limits of this setup

No GPU, no high availability, no load balancer, no proven production SLA, no restore drill, no tested high concurrency, no installed external monitoring, no automatic credential rotation, no actual Vercel end-to-end verification, and no production model-quality acceptance. Public API is intentionally restricted to models and chat; management must use SSH.
