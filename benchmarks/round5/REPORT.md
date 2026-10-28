# Round 5 results

Three new variants, measured separately for English and image recognition. No moderation, non-English, movie or multi-image claims.

| Model | Outcome | Result |
| --- | --- | --- |
| gemma3:270m | completed | 3/14 English checks |
| hf.co/LiquidAI/LFM2.5-350M-GGUF:Q4_K_M | completed | 6/14 English checks |
| minicpm-v4.6:q5_K_M | completed | 32/32 valid; reference readiness 0.931; median 24.93s |

## Method and limits

English uses the same seven frozen prompts, each run twice (14 checks), plus a separately scored native tool call. Repetition is not 14 independent scenarios. Granite was rerun as a fresh complete English control.

The image candidate uses all 32 frozen recognition images, nine paired robustness variants and eight count probes. It calls the exact deployed Camera recognition Runner with normalized images under a renewable idle maintenance lease. This measures the service implementation, not HTTPS/queue latency. Eight fresh current-winner sentinel images detect regression; the full current-winner score is historical, not a fresh paired full-cohort rerun. No new unseen holdout or independent human adjudication was added.

No production payloads or training exports. Temporary inputs are approved public research fixtures. Per-request guards give production work opportunities between image cases. Declined temporary weights are removed, digests/evidence retained. Context, memory cap and CPU allocation unchanged. Historical speed comparisons can vary with cache and load.

See [raw run](results.json), [plan](plan.json), [source revisions](source-metadata.json), [per-case image scores](recognition-summary.json) and [merged task rankings](rankings.json).

Current ranking leaders: English **granite4:1b-h**, recognition **minicpm-v4.6:q5_K_M**. Deployment verification is recorded separately.

Paired readiness difference versus historical Q4 baseline: 0.1236; descriptive 95% bootstrap interval [0.0257, 0.2419]. A range spanning zero does not establish a reliable quality improvement.

## Resource and comparison caveats

Sampled cgroup memory reached the 2800 MiB container ceiling, including page cache; no OOM kills were observed. This remains memory-tight CPU inference, with one model/job at a time. Q5 scored 7/8 counting probes, against an always-one reference baseline of 6/8; this is not broad counting certification. The new explicit non-thinking profile and historical Q4 baseline mean the gain cannot be attributed solely to quantization. A full fresh Q4/Q5 comparison with identical profiles is tracked in the backlog.

## Live deployment verification

Policy `94fd64780e8bf6b8f8946611fb37d4ce80816b93b2771cf7d1e009ec28dc853d` was deployed and 45 authenticated public HTTPS checks passed, including ranked auto image/text selection, mixed FIFO serialization, independent moderation and explicit alternatives, and result deletion. The explicit new recognition variant was honored and default text was restored afterward. Cleanup resumed; gateway, chat and monitoring were active. Temporary server image copies were removed; evidence and approved local research fixtures remain.
