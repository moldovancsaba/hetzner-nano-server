# Apertus Hungarian follow-up — 2026-10-28

**No replacement passed the unchanged Hungarian gate. Do not promote these profiles or enable unattended Habi coaching.** The current Qwen3 4B Q3 short-context route stays explicitly experimental; neither loading a model nor allocating more context establishes usable Hungarian quality.

| Exact tested profile | Strict structured | Valid JSON | Usable original chat | Usable Habi regressions | Median native inference | OOM kills |
| --- | --- | --- | --- | --- | --- | --- |
| Apertus v1.1 0.5B Instruct Q4_K_M, ctx4096/batch8 | 2/24 | 23/24 | 2/6 | 0/5 | 1.52 s | 0 |
| Apertus v1.1 1.5B Instruct Q4_K_M, ctx4096/batch8 | 3/24 | 24/24 | 2/6 | 0/5 | 2.89 s | 0 |
| Historical Qwen3 4B Instruct-2507 Q3_K_M, ctx1024/batch8 | 17/24 | See Round 1 | 3/6 | Client's separate seven-sample probe failed quality | See Round 1 | 0 in selected profile |

Frozen acceptance remains >=20/24 strict structured + >=5/6 usable original chat, complete execution and no OOM. Native timings exclude HTTP queue waiting; profiles have different context/quantization. Community GGUF Q4 results do not prove identical performance for upstream full-precision weights or other quantizations.

## What was tested

Seventy native calls: the unchanged 24 structured + six free-form Hungarian cases for each candidate, followed by five synthetic cases adapted from Habi's evaluation script. The Habi cases use the benchmark's generic Hungarian system instruction and 192 output tokens, so they are a separate diagnostic set, **not an exact replay of the client's seven calls**. No actual coaching conversations or customer data were accessed or retained.

Strict scoring checks exact key sets, values and JSON types; numeric strings do not pass numeric fields. Expected answers never enter prompts/schemas. Original chat criteria remain frozen and assistant-reviewed, not an independent native-speaker review. Habi diagnostic cases preserve role/correction/fact requirements separately; they do not alter the original gate.

Failures included wrong/missing fields, repetition, invented numbers, assistant/coach role confusion, unsupported causal explanations and contradictory meal corrections. The 1.5B profile used more context but still reproduced the client's kind of failures. Supplying useful history is required in a stateless API, yet these single-turn failures cannot reasonably be explained only by absent conversation memory.

## Hardware and context evidence

Hetzner CAX11, two shared ARM64 CPUs, 4 GB host RAM, unchanged 2800 MiB Ollama cap, CPU only. Models were staged one at a time under a renewable idle gateway lease, cleanup paused during experiments, then temporary weights removed and Granite restored. Existing client work could run between bounded cases. No swap/cap increase or production default change.

Measured peak native-container usage: about 1793 MiB for 0.5B, 2800 MiB for 1.5B. This includes runtime/cache accounting and is not just weight size. Both completed with zero OOM-counter increase. The 1.5B profile approaches the cap; 4K allocation was tested on short prompts, **not a 4K recall/long-conversation test or an approved service context**.

Official Mini configs declare 4096 maximum positions. Original Apertus 8B and later larger families have different context specifications. Do not advertise a larger family's context as the tested Mini service limit. Official MLX/NVFP4 packages are not CPU Ollama deployment artifacts; the measured packages were community GGUF conversions.

## Reproduction and evidence

- `plan.json`: exact model identifiers, quantization, upstream/conversion revisions and resource profile.
- `fixtures.json`: frozen original cases and five synthetic diagnostic additions.
- `results.json`: synthetic-only outputs, installed digests, timing, cgroup peaks, cleanup/restoration outcome.
- `chat-review.json`: explicit assistant judgments and limitations.
- `rankings.json`: strict scores and unchanged gate.
- `source-audit.json`: official model metadata and prospective larger candidates; metadata-only checks are not inference tests.

Stage this folder's run/plan/fixtures in `/opt/narimato-benchmarks/hu-round2` beside the existing `round4` helper. Run with the same root-only maintenance guard and verify free disk before installation. `prepare.py` additionally reads Habi's synthetic evaluation script; freeze/copy fixtures before inference rather than depending on a changing client checkout. The runner removes only candidates absent from its initial inventory. Do not rerun unchanged failures without a changed-condition reason.

## Decision

Keep Apertus Mini metadata/results, remove its temporary binaries, preserve existing ranked defaults. Research Phi-4 Mini and Hungarian-adapted PULI on a host with enough RAM and disk for useful quantizations/context. Racka's research-only terms block adopting it for the commercial service. Before any replacement, require both the original gate and fresh Habi-specific role/date/correction/grounding checks. See [client audit and options](../../../docs/HUNGARIAN-FOLLOWUP.md).
