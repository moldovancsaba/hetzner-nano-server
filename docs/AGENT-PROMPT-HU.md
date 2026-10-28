# Agent prompt: experimental Hungarian text

Integrate the experimental Hungarian service documented at https://github.com/moldovancsaba/hetzner-nano-server/blob/main/docs/HUNGARIAN.md.

Use https://chatbotapi.haho.ai/v1 with this project's own LOCAL_AI_API_KEY in the server/runtime environment. Never expose the key in browser code, chat or logs.

For explicitly Hungarian requests, submit POST /v1/jobs with Authorization: Bearer <project key>, Content-Type: application/json and a stable Idempotency-Key. Example body:

```json
{"task":"text_chat_hu","model":"auto","input":{"messages":[{"role":"user","content":"Kérlek, segíts röviden magyarul."}],"temperature":0,"max_tokens":128}}
```

Poll GET /v1/jobs/{id} every 2–5 seconds using the same credential. Resume that job after timeouts; do not resubmit duplicate work. Respect Retry-After for 429/503. On completion, read result.choices[0].message.content, check finish_reason and validate any requested JSON. DELETE the terminal job after consuming it. Use X-Request-Purpose: test only for synthetic tests and operator checks.

Discover availability and the experimental flag using GET /v1/job-types and /v1/models. Keep English requests on text_chat. Never silently fall back to English or install models.

This is a short-context experimental service: 1024 context, output recommended 128 and maximum 192 tokens. With 128 output tokens, the serialized messages budget is 640 UTF-8 bytes, including framing/system instructions. Leave room for the server's default Hungarian instruction if no system message is supplied. Split sources/history; preserve accents. Hungarian tool calls and OCR are not supported. Retrieve authorized listings outside the model and pass only a small relevant excerpt.

IMPORTANT: The model scored 17/24 structured cases and 3/6 usable conversational replies; it did not meet the production-readiness gate. Require human review, verify claims against trusted data, and never turn its output directly into publication, database changes or consequential decisions. JSON schema constrains format, not truth. Do not log customer conversations or use them for training.
