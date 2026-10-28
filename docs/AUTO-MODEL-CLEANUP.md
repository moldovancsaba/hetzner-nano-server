# Automatic model-weight cleanup

Owner policy, updated 2026-10-28: retain **the top three models in each current job-specific ranking**, plus models used by valid non-test inference requests in the last **14 days**. This replaces the previous permanent alternative pins and seven-day rollback-cache target.

## What stays

For every installed model, retain it if any condition applies:

1. It is a current default, or has rank 1–3 in **any** current job ranking (English text, general image recognition, moderation and experimental Hungarian text separately).
2. An authenticated, validated, successfully admitted **production** inference request selected it within the past 14 × 24 hours.
3. It is resident in Ollama, or service work is active/queued. Cleanup waits/skips rather than disrupting work.
4. During the initial migration only: it was in the initial installed inventory and tracking started less than 14 days ago. This avoids pretending we know the previous two weeks of usage.

The union is intentional: a rank-six text model can still be a top-three image model. Missing top-three weights are **not downloaded automatically**; this is an eviction policy, not an installation job. Uninstalled artifacts and previous outcomes remain in the model-policy/test index and versioned reports.

Everything else is eligible for removal of its **weights only**. No benchmark evidence, declined-model metadata, rankings, training datasets, labels, approved adapters, credentials or application data is deleted by this cleaner.

## Valid use and test exclusion

The default purpose for an authenticated inference submission is `production`. It counts only after input/model/permission validation and queue-capacity checks pass and the job is admitted. Requests rejected as invalid, unauthorized, unavailable or queue-full do not count. Requests that later fail inference or are cancelled still represented valid admitted demand and remain counted.

Tests must send:

```http
X-Request-Purpose: test
```

Production clients can omit the header or send `production`. Any other purpose is rejected. Health checks, polling, model discovery, job deletion and metadata collection never count. Duplicate idempotent submissions do not create another demand event; purpose is part of the request fingerprint. The server cannot infer whether arbitrary unmarked content is a test—unmarked inference is treated as production.

All repository verification tools, the synthetic benchmark and the Camera operator-test helper now mark their calls as tests. Pandora forwards a supplied test marker for authorized UI verification; ordinary browser chat defaults to production. Future tools/agents must use the test header. Direct native Ollama benchmarks do not pass through this tracker and do not extend production retention.

## Metadata retained

The gateway's private `/var/lib/narimato-gateway/model-usage.json` contains:

- initial tracking timestamp and installed model/digest bootstrap inventory;
- per model: last admitted production-request timestamp, aggregate production-request count and artifact digest.

No prompt, answer, image, image hash, result evidence, job ID, user ID, tenant ID or API key is written to this usage store. It survives gateway restarts. Atomic replacement and filesystem sync happen before admitting production work. If usage cannot be recorded, admission returns 503 rather than silently accepting untracked work that the cleaner might evict.

Model-use metadata is operational aggregate information, not a production content archive or training capture. The existing five-minute RAM result retention and explicit DELETE behavior are unchanged.

## Schedule and concurrency safety

Units: `narimato-model-cleanup.timer` and `narimato-model-cleanup.service`. The timer runs **hourly with up to five minutes of randomized delay**, and catches up after downtime. It is separate from daily metadata discovery.

The cleaner obtains a short-lived exclusive maintenance lease from the gateway only when the queue is empty, no job is active and the inference circuit is healthy. While held, new inference submissions receive retryable 503; discovery and result reads continue. If the gateway is busy or another lease exists, the run skips and retries at the next timer. Cleanup does not terminate queued/running work to make space.

The gateway's maintenance endpoint is loopback-only, omitted from Caddy's public routes, and protected by its own root-managed key. Project keys cannot acquire or renew a cleanup lease. The cleaner renews its five-minute lease before removal, rechecks policy, usage, digest and loaded models, and releases the lease in `finally`. The private lease is persisted separately from usage metadata and survives a gateway restart, so a deletion already in flight cannot lose its admission guard. If the cleaner process fails, the lease expires. The systemd operation timeout is shorter than the lease lifetime; deletion commands have their own timeout.

It records model identity/digest and the proposed decision **before** deleting with `ollama rm`. Shared blobs remain when referenced by another model; reported model sizes do not equal physical disk recovered. If policy, usage, gateway, inventory, lease or deletion checks fail, it stops rather than guessing that a model is unused.

No cleaner can safely coordinate arbitrary direct native calls made outside the gateway. **Before operator benchmarks/download experiments, pause this timer and drain production traffic**; restore/verify services and re-enable it afterward. Do not let an unranked temporary candidate sit unprotected between native test stages while hourly cleanup is enabled.

## Initial grace period

We had no trustworthy non-test production-use ledger before this rollout. Existing weights therefore get one initial 14-day history grace period. Current top-three/default models remain protected afterward. Lower-ranked existing models without admitted production use will become eligible once that grace expires; tests do not restart or extend it. Newly installed models do not inherit the initial inventory grace.

The cleaner was verified using a disposable unranked model alias created **after** tracking initialized. It removed that alias while preserving the source model and all current installed weights covered by rank, residency or initial grace. No genuine production use was manufactured to test retention.

## Operations

Code: `/opt/narimato-model-cleanup/cleaner.py`.

Policies/evidence: `/opt/narimato-gateway/config/model-policy.json`, `/opt/narimato-ai/model-storage-policy.json`, private gateway usage JSON.

Maintenance key: `/etc/narimato-model-cleanup.env`, root-only; also read by the gateway unit. Do not copy it into project/browser environments or public docs.

Audit state: `/var/lib/narimato-model-cleanup/latest.json` and timestamped metadata-only cleanup reports. These preserve deletion identities/digests and keep reasons; model/test history remains in Git independently.

```sh
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'systemctl list-timers narimato-model-cleanup.timer --no-pager'
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'systemctl start narimato-model-cleanup.service'
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'cat /var/lib/narimato-model-cleanup/latest.json'
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'journalctl -u narimato-model-cleanup.service -n 20 --no-pager'
```

Disable with `systemctl disable --now narimato-model-cleanup.timer`. Before changing gateway/storage code or secrets, inspect the queue and active maintenance lease, stop the timer and drain work. The historical `retire_declined_models.py` helper refuses weight deletion under policy v2; the common cleaner now owns those decisions.

To restore an evicted alternative, an authorized operator must pull the exact tested artifact, verify its digest and eligibility, and let API discovery refresh. There is no public model-install endpoint. A lower-ranked model without recent production use may be evicted again; a legitimate admitted request restarts its 14-day demand window.

See [verification](../results/auto-cleanup/README.md), [retention policy](DATA-RETENTION.md) and [model-selection policy](MODEL-POLICY.md).

## Top-three rollout, 2026-10-28

The hourly cleaner now retains ranks 1–3 in each of the four routes: English text, image recognition, image moderation and experimental Hungarian text. Hungarian currently has only one eligible experimental profile; this does not imply three approved Hungarian models. The first run completed, removing two unprotected packages (LFM2.5-VL-450M Extract Q8 and Qwen2.5 0.5B), leaving 20 installed packages. Older inventory still has its original history grace; recent non-test demand remains protected. No history or benchmark results were removed.
