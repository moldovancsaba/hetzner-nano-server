# Hungarian client audit and Apertus follow-up — 2026-10-28

## Client implementation audit

Read-only inspection of Habi's `worker/evaluations/hungarian_route.py`, `worker/habi_worker/shared_ai.py` and `docs/coach-message-history.md` confirms two different paths:

- The normal hosted worker hardcodes `text_chat` and therefore selects the English-ranked model. A model override on that task is not a substitute for `text_chat_hu`.
- The seven-sample synthetic Hungarian evaluation explicitly uses `text_chat_hu`, `model: auto`, system/user message roles, temperature zero, 128 output tokens and the test-purpose header. It polls terminal results, inspects truncation and deletes consumed jobs. The focused version explicitly separates assistant and coach roles.

The gateway's `gateway/hungarian.py` deep-copies messages into native `/api/chat` without flattening roles. No obvious request-format defect explains the reported invented date, role confusion or fabricated causes. This is a source audit, not access to the exact historical HTTP bodies or a complete browser/database replay. Long-input rejection and `finish_reason: length` must still be handled. Each evaluation case is an independent request; the service does not maintain conversational memory. Real follow-ups must include bounded relevant history or an application-maintained state summary.

Do not enable the experimental route for unattended coaching. Keep names, dates, facts and corrections in validated application state. A model must not supply the current date or reconstruct missing history from its weights. Passing a known date can remove ambiguity but cannot establish factual reliability.

## Apertus: distinguish model families and real service limits

Official sources now include [Apertus Mini](https://apertus-ai.org/articles/2026-06-apertus-mini/) and [0.5B/1.5B/4B Instruct checkpoints](https://huggingface.co/collections/swiss-ai/apertus-mini). The pinned Mini configs report **4096 maximum positions**. This is distinct from the original [8B Instruct's 65,536-token model limit](https://huggingface.co/swiss-ai/Apertus-8B-Instruct-2509) and later larger releases. MLX quantizations target Apple hardware; NVFP4/vLLM artifacts are not drop-in CPU Ollama weights.

We evaluate community GGUF Q4_K_M conversions of the official 0.5B and 1.5B Instruct models, recording upstream/conversion revisions and installed digest. Run at 4096 context / batch 8 under the unchanged 2800 MiB native runtime cap. Native context allocation does not prove long-context recall: this follow-up uses the frozen short-case benchmark. No new public context allowance or Hungarian default is promised merely because a model loads.

[Round 2 report](../benchmarks/non-english/hu-round2/REPORT.md) preserves the original 24 strict structured cases and six chat criteria, plus five separate synthetic Habi regressions. Client regressions are not folded into the original acceptance threshold. No live coaching conversations are retained.

## Measured outcome

Both Mini candidates completed 35 calls each with zero additional native OOM kills. At ctx4096/batch8, the 0.5B Q4 profile scored 2/24 structured and 2/6 usable original chat; the 1.5B Q4 profile scored 3/24 and 2/6. Each failed all five separate Habi regressions. Neither passes the original gate or replaces the Qwen experimental profile. Temporary weights were removed, evidence retained and services restored.

## Other candidates and constraints

| Candidate | Reason to consider | Current constraint / next decision |
| --- | --- | --- |
| [Phi-4 Mini Instruct](https://huggingface.co/microsoft/Phi-4-mini-instruct) | Official multilingual instruction model, Hungarian among supported languages, 128K advertised context | 3.8B; low-bit weights, runtime buffers and KV cache need an explicit memory/disk preflight; advertised context is not our usable service context |
| [PULI-LlumiX Llama 3.1](https://huggingface.co/NYTK/PULI-LlumiX-Llama-3.1) | Hungarian-adapted 8B model from the language research institute | Larger hardware required for a useful quantization and context on this service; not tested here or proven better for Habi |
| [PULI Qwen-based adaptation](https://wolala.nytud.hu/wp-content/uploads/2025/11/wolala___PULI_hun_full.pdf) | Hungarian continual pretraining plus instruction tuning | 7B class; same hardware/quality gate issue; evaluate on a larger host before use |
| [Racka 4B](https://huggingface.co/elte-nlp/Racka-4B) | Hungarian-adapted tokenizer and training; local research interest | Gated research-only CC-BY-NC-SA model, not a commercial-service candidate under its published access terms; no deployment proposed |
| [EuroLLM 9B / 22B](https://eurollm.io/) | EU multilingual family including Hungarian | Larger than current host; earlier 1.7B failed our unchanged Hungarian gate |

Broad multilingual training or a larger context window does not establish Hungarian instruction following or faithfulness. For a dependable coaching assistant, the practical next evaluation is a useful 4B–8B quantization with more RAM, or an explicitly selected external service. Hardware upgrades and external inference are not performed by this documentation change. Preserve the local fallback's experimental status until measured replacement evidence passes the original gate and Habi-specific regressions.

## Round 3 (2026-10-29): LFM2 1.2B and OLMo 2 1B

Two further small checkpoints ran the same 35 frozen Hungarian cases at ctx2048/batch16 as part of [Round 6](../benchmarks/round6/REPORT.md), scored separately from English. LFM2 1.2B Q4_K_M scored 2/24 strict structured and OLMo 2 1B Q4_K_M 0/24, against the unchanged 20/24 gate and 17/24 for the served Qwen3 4B Q3 profile. Neither is a candidate, so the free-form review and the Habi regressions were not performed (recorded as not performed). Zero OOM kills. The served experimental route and its limits are unchanged. [Scores](../benchmarks/non-english/hu-round3/rankings.json).
