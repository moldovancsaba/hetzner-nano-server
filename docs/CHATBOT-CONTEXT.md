# Why chatbotapi now has 8K context

Decision and deployment: 2026-10-27. Paperclip remains at 8K. The default Granite 4 1B Hybrid text routes for ClassScout, Habigoal and Pandora now also provide an 8192-token total context window on the same existing inference host.

## Reasoning

The previous 2048-token context was suitable for narrow extraction, but constrained conversations, source passages, listings, instructions and tool definitions. Pandora further restricted input to 1800 characters per message and kept only six prior messages in the browser, while its backend retained at most 2600 characters. Raising the model allocation alone would not have made longer conversations usable.

Our matched-input 4K-versus-8K test found essentially the same processing time: 1203 tokens took 27.702 versus 27.586 seconds, and 1995 tokens took 42.590 versus 43.016 seconds. Larger actual input takes longer; reserving a larger window did not produce a meaningful short-request slowdown in this small sample. These totals include model loading and are not a latency guarantee. See ../benchmarks/paperclip-context/COMPARE-4K-8K.md.

The 8K runtime passed the existing fourteen English structured checks and a 6892-token native long request after we capped the prompt cache at 128 MiB and checkpoints at two. Without those cache limits, repeated requests exhausted the container even after a successful single long request. Keep the cache limits and single-generation policy; do not blindly increase every installed model's context. More context allows the model to use more supplied evidence and history; it does not establish stronger reasoning, factual reliability, non-English support or autonomous research capability.

## Effective limits

| Caller | Default Granite context | Output limit | Longer inputs |
| --- | --- | --- | --- |
| ClassScout API | 8192 total tokens | Up to 1024; default 256 | Token-budget checked; async required above 4096 counted input tokens |
| Habigoal API | 8192 total tokens | Up to 1024; default 256 | Same |
| Pandora API | 8192 total tokens | Up to 1024; default 256 | Same |
| Pandora browser chat | 8192 total tokens | 256 | Backend submits/polls async jobs; history trimmed by actual token budget |
| Paperclip | 8192 total tokens | Up to 1024; default 256 | Existing profile retained |
| Explicit alternative text models | Their previously tested profile, generally 2048 | Existing limit | No untested automatic context increase |
| Camera image routes | Existing 2048 profiles | Existing limits | Unchanged |

The gateway reserves 1536 tokens for template overhead and, in addition, the complete requested reply (`max_tokens`). At the default 256-token output budget, up to 6400 counted input tokens are available; with a 1024-token reply, up to 5632 remain. Submitted instructions, messages, history, tool calls and schemas all share that input allowance. The gateway accepts text bodies up to 256 KiB, but the tokenizer remains the actual admission guard. (Pandora's `/chat` route is stricter: Caddy limits its bodies to 128KB.) Over-budget API input is rejected before queue admission.

Use model auto for the ranked default. Future default changes require a verified 8K profile for each covered text tenant; an unverified new winner fails explicitly rather than silently falling back to a smaller context. Deliberate explicit model pins keep their actual tested limits. Discovery reports the effective per-tenant profile.

## Pandora conversation handling

The browser now accepts up to 24000 characters per message and retains up to thirty prior messages for the next request. The backend keeps the system instruction and newest complete turns that fit the token budget, warns when older history was omitted, and rejects an over-budget latest message instead of silently cutting it off. Displayed messages remain only in the tab; the change does not add durable conversation storage. Request size is limited before the backend sees it: Caddy refuses `/chat` bodies over 128KB with a 413 (`config/Caddyfile.example`), and the backend applies the same 128,000-byte limit (`chat/server.py`). Thirty messages of 24000 characters can exceed 128KB, so a very long conversation can be refused before the token-budget trimming runs.

The backend uses the same asynchronous gateway jobs as other clients and polls for completion, so a long prompt is not bounded by the old 110-second upstream request timeout. It deletes completed jobs after delivering the reply. Only one chat generation is allowed at a time. The model queue is still shared across text, images and Paperclip; long inputs can delay other callers. The shared password, same-origin checks and protected backend key remain in place. Refresh Pandora and unlock it again after deployment because service restart invalidates the previous in-memory session.

## Verification and scope

35 relevant tests passed: token-aware chat history, model policy/context scope, gateway routing, long-context conversion and retention. Public synthetic verification completed input beyond 2048 tokens under each of the three chatbotapi credentials, and verified all four 8K default profiles plus a deliberate 2K Qwen alternative. Pandora retained a code from the start of an eleven-message conversation, beyond its old history limits, with actual prompt usage above 2048 tokens. An oversized newest message was rejected before inference. A real-tokenizer dry check trimmed a 21-message oversized history to eleven messages / 6216 counted input tokens while preserving the newest user request.

See ../benchmarks/chatbot-context/public-verification.json. The service remained within its memory limit during those checks. No model weights, language approval, application database, Vercel Production environment, external messages or recurring job schedules were changed. Application clients must submit larger inputs to benefit; long work should use submit/poll requests compatible with their hosting timeouts. A full browser visual test was not performed.

Sources of deployed behavior: config/runtime-context-profiles.json, generated config/model-policy.json, gateway/catalog.py, gateway/server.py, gateway/long_context.py, chat/context.py and chat/server.py. The global Ollama fallback remains 2048; verified request profiles set 8192 explicitly. The controlled deployment backup is /opt/narimato-ai/chatbot-context-backup-*.
