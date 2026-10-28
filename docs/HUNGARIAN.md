# Hungarian text API — experimental

**Available for deliberate testing and feedback. Not approved for unattended production decisions.** The best tested profile is Qwen3-4B-Instruct-2507 Q3_K_M, served as `text_chat_hu`. All original quality gates remain visible: **17/24 structured cases and 3/6 usable assistant-reviewed chat replies**. No candidate met the 20/24 + 5/6 acceptance gate. This is the best measured option in this environment, not a claim of reliable general Hungarian fluency.

[Copy the agent prompt](AGENT-PROMPT-HU.md) · [Full evaluation](../benchmarks/non-english/hu-round1/REPORT.md) · [Public dashboard](https://chatbotapi.haho.ai/benchmarks/).

## Call the service

Base URL: `https://chatbotapi.haho.ai/v1`. Use your project's existing bearer key, usually `LOCAL_AI_API_KEY`. ClassScout, Habigoal, Pandora and Paperclip may call this job; Camera keys cannot. Do not reuse another project's key. No new public or shared credential is needed.

```http
POST /v1/jobs
Authorization: Bearer <your project key>
Content-Type: application/json
Idempotency-Key: <stable unique key for this exact request>
```

```json
{
  "task": "text_chat_hu",
  "model": "auto",
  "input": {
    "messages": [{"role": "user", "content": "Kérlek, segíts röviden magyarul."}],
    "temperature": 0,
    "max_tokens": 128
  }
}
```

The response is HTTP 202 with an opaque job ID. Poll `/v1/jobs/{id}` every 2–5 seconds with the same key. Resume the same job after a client timeout; do not duplicate work. Retry 429/503 according to Retry-After, preserving POST body/idempotency key. Check terminal status; content is `result.choices[0].message.content`. Treat a `length` finish reason as incomplete. After consuming a terminal result, DELETE `/v1/jobs/{id}`. Results otherwise expire after five minutes; the queue is memory-only.

`GET /v1/job-types` exposes the selected model, alternatives and `experimental: true`. `/v1/models` exposes its tested digest/profile. Use task `text_chat_hu` and model `auto` to follow future independently tested Hungarian improvements. `/v1/chat/completions` continues to select the English task; it does not switch languages automatically.

## Tested resource limits

- Context **1024**, batch **8**, non-thinking, one shared FIFO worker. The original 2048/batch32 attempt caused an OOM; the smaller profile completed all 30 cases with zero additional OOM kills.
- Output defaults to **128 tokens**, maximum **192**. Keep answers brief.
- Serialized UTF-8 `messages` must fit `min(1000, 1024 - requested_output_tokens - 256)` bytes, including role framing and any system message. With 128 output tokens the limit is **640 bytes**. The server adds a short Hungarian system instruction only if none is supplied; leave space for it. Split retrieved sources and discard unnecessary history. Do not strip Hungarian accents to meet the budget.
- Response-format JSON is limited to **1536 UTF-8 bytes**. A JSON schema can enforce field names/types; it does not make factual values correct. The full accuracy benchmark used JSON-object mode; only an API integration example used a schema.
- Hungarian tool calling, long conversations, Hungarian OCR and automatic language detection are not approved. Retrieve authorized data in the calling application, then supply a short relevant excerpt. Human review is required for factual recommendations, prices, addresses and actions.

Client requests default to declared production purpose. Synthetic tests and operator checks must send `X-Request-Purpose: test`; do not mislabel real usage to manipulate retention. Request bodies/replies are transient, never captured for training. Existing English/image/moderation defaults and their scores remain independent.
