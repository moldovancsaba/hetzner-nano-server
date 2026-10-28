# Round 5 — tiny English models and image quantization

Run started 28 October 2026. See [plan](plan.json), [source metadata](source-metadata.json), and, when completed, REPORT.md and results.json.

New English variants: Gemma 3 270M and LiquidAI LFM2.5 350M Q4_K_M. New image variant: MiniCPM-V 4.6 Q5_K_M versus the existing Q4_K_M package. These are three new model IDs, not three new model families.

The runner reuses the Round 4 English fixtures/validators and calls the deployed image Runner directly. Every native work unit requires a renewable idle gateway maintenance lease. Existing client jobs finish first; new submissions can receive retryable maintenance responses during a unit. Two-second gaps between image units give client work opportunities. Cleanup is paused during the batch and restored in finally; no runtime restart, cap change or swap is introduced.

## Reproduce

Stage run.py, plan.json and the frozen vision-evaluation/recognition-manifest.json in `/opt/narimato-benchmarks/round5`. Copy only manifest-listed approved research image files from ignored `private/vision-evaluation/images` to its inputs/ directory. Use the gateway venv so image normalization and the exact deployed implementation share dependencies. Round 3 fixtures and Round 4 runner must already exist in sibling directories.

```sh
systemd-run --unit=narimato-benchmark-round5 --property=Nice=10 --property=TimeoutStopSec=180 /opt/narimato-gateway-venv/bin/python /opt/narimato-benchmarks/round5/run.py
journalctl -u narimato-benchmark-round5 --no-pager
```

Do not start a duplicate run. Results are checkpointed after each case. The runner records sampled peak cgroup memory, OOM deltas, cold load/unload timing and exact model digests. New candidate weights are removed after evaluation; eligible winning/top-five artifacts are reinstalled during reviewed policy publication. Preserve evidence even for failures. Remove temporary server image inputs when finished.

After results are copied back, run report.py, update canonical ranking-source pointers/digest evidence, regenerate/check policy and tested index, deploy/verify eligible defaults and explicit selection, then rebuild/publish the dashboard. No moderation or non-English ranking is changed by this round.
