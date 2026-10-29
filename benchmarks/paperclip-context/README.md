# Paperclip context feasibility tests

2026-10-27. Native synthetic inference on the existing ARM64 4 GB / 2-vCPU host. Ollama 0.40.11, pinned image from config/compose.yaml, 2800 MiB container cap, Granite `granite4:1b-h`, one inference at a time. No paid API or provider subscription used.

Tests pause the cleanup timer, acquire/renew the exclusive gateway maintenance lease, then restore the timer and release the lease. Production jobs are not run concurrently with native tests. Prompts and results are synthetic test evidence, not retained production traffic. The generation monitor samples memory every second and aborts at low host memory or an observed OOM-kill increase. An HTTP error causes a controlled container restart while exclusive; kernel logs must also be checked, because the one-second sampler can miss a fast OOM followed by restart.

`probe.py` is the final 8K target runner: a calibration prompt, a long prompt with three synthetic codes, native tool selection and a tool-result answer. `compatibility.py` runs the same seven English structured cases twice, followed by the tool round trip. It imports the existing round3 fixtures copied to the probe directory on the server. These tests do not certify an autonomous agent, general research quality, non-English support or sustained concurrent capacity.

Preserved unsuccessful evidence:

- `short-32k.json`: 32K allocated and a short READY response; not a full-window pass.
- `batch32-partial.json`: 32K long-input run stopped after ~5,504 tokens / 182 seconds to evaluate a larger prefill batch.
- `batch128-32k-partial.json`: stopped when the owner changed the target to 16K; no completed full-window 32K result.
- `results-16k.json`: 14,452-token long prompt completed in 340.645 seconds; tools worked; no new OOM in that run. All three codes were found, but trailing punctuation prevents an exact-value pass without normalization.
- `compatibility-16k-attempt.json`: subsequent short requests failed; kernel evidence confirms the runner was OOM-killed. A successful long request did not establish safe repeated use.
- `compatibility-16k-fresh-partial.json`: a fresh-run diagnostic was stopped when the owner clarified the target should be 8K. Ten passing short checks do not override the earlier failure.
- `results-8k.json`: 6,892-token long prompt completed in 142.796 seconds, followed by successful tools. Punctuation caveat is unchanged.
- `compatibility-8k-attempt.json`: subsequent short requests also OOM-killed the runner. Therefore reducing the context alone was not accepted as a fix.

The bundled llama-server's own `--help` and startup logs identified a default 8192 MiB prompt-cache allowance and 32 context checkpoints. The inference container's total limit is only 2800 MiB. `bound_cache.py` sets `LLAMA_ARG_CACHE_RAM=128` and `LLAMA_ARG_CTX_CHECKPOINTS=2`, keeping the global default context at 2048. Logs confirmed the effective limits. The original Compose file is saved on the server at `/opt/narimato-ai/compose.before-context-cache.yaml`. Final bounded-cache results and conclusions are recorded alongside this report after validation.

## Accepted 8K profile

With the bounded cache, the native long request completed 6892 prompt tokens in 143.260 seconds, followed by successful native tool selection and a tool-result answer. The same seven English structured cases then passed 14/14, with no new OOM kills. See results-8k-bounded-cache.json, compatibility-8k-bounded-cache.json, bounded-cache-runtime.json and summary.json. Raw code extraction retained trailing punctuation; capacity acceptance does not turn that into an exact-format success.

The generated policy gives only the `paperclip` tenant an 8192-token total window, max 1024 output tokens, num_batch 128 and a 900-second native deadline. All other tenants retain 2048-token profiles and their existing request limits. Paperclip uses a verified tokenizer with a 1536-token conservative template reserve plus the complete requested output reservation, so not all 8192 tokens are available for user text. Oversized requests fail before queue admission. A missing/changed model or missing verified context profile fails explicitly; unverified alternatives are shown as unavailable to Paperclip.

Long Paperclip requests must use async jobs rather than hold a synchronous HTTP request. At most one Paperclip job may be pending, and the underlying FIFO still permits only one generation at a time. Long work shares CPU capacity with other projects and can delay them; these tests do not establish a service-level latency guarantee.

The final public API test accepted 4113 prompt tokens, retained a code from the beginning, returned the exact requested JSON under an explicit schema, and recorded the 8192-token model profile. Its 4.492-second result was a warmed/repeated-prefix request, not a cold long-input latency claim. Oversized input and unauthorized image jobs were rejected. The first public attempt found the correct code but returned incorrect field names under json_object; that failure is preserved in public-verification-first-attempt.json. Schema-constrained verification is in public-verification.json.

Existing ClassScout/Habigoal authentication checks passed, tenant discovery confirmed Paperclip=8192 and ClassScout/Habigoal/Pandora=2048, and actual existing text, general image and moderation fixture generation completed. Relevant gateway, policy, token-budget and retention tests passed (29 total). No new ranking winner, model artifact, provider subscription, autonomous agent, external outreach or recurring research job was introduced. The gateway now uses a tokenizers-enabled venv; the initial recovery archive on the owner's Mac was refreshed with the independent Paperclip connection credential and metadata.

## Matched 4K versus 8K comparison

[Matched-input speed and usable context comparison](COMPARE-4K-8K.md): no meaningful speed advantage for 4K in the four-call sample; retain the approved 8K Paperclip profile. The comparison introduced no production setting change.
