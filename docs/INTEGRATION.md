# Application integration

Both applications run on Vercel. Call the service from a server-side function with application authentication, input validation, and rate limiting. Never call it from a browser with the bearer key.

```dotenv
LOCAL_AI_BASE_URL=https://chatbotapi.haho.ai/v1
LOCAL_AI_MODEL=auto
LOCAL_AI_API_KEY=<correct-project-key>
```

The chat route is `POST https://chatbotapi.haho.ai/v1/chat/completions`. Use the existing SDK's baseURL setting or standard HTTP. Do not append `/v1` twice. The model inventory route is `GET /v1/models`.

Example request body:

```json
{
  "model": "auto",
  "messages": [{"role": "user", "content": "Summarize this short text in one sentence: ..."}],
  "reasoning_effort": "none",
  "temperature": 0.2,
  "max_tokens": 128,
  "stream": false
}
```

Supply `Authorization: Bearer <key>` and `Content-Type: application/json`. For JSON, add `response_format: {"type":"json_object"}`, ask for the required fields, then parse and validate the result against a schema. Valid JSON is not evidence of factual correctness.

Keep input plus output within the 2,048-token context budget; an application must enforce its own limits. Request body is capped at 128 KB by Caddy, which is not a token limit. The runtime queue and memory limit are not substitutes for product quotas. Keep output short, use bounded timeouts compatible with the project's Vercel function duration, handle 401/413/429/503 and network errors, and avoid retry storms. Exact runtime error status depends on the failure path.

Use classification, simple extraction, short summaries, and brief suggestions as initial candidates. Do not rely on complex reasoning, tool use, long histories, high concurrency, or unvalidated factual answers. Evaluate multilingual project examples explicitly.

Preserve existing working integrations until task-specific evaluation passes. Do not silently route sensitive requests or incur costs through a fallback provider. No task-specific production workflow was implemented by the server setup.

## Thinking control

Native `/api/chat` accepted `think:false` locally, but native management routes are not public. An initial OpenAI-compatible request relying only on `/no_think` consumed the 100-token output cap and produced empty final content. Explicit `reasoning_effort:"none"` produced valid JSON in the next test. Use this field rather than relying on prompt text.

## Agent handoff

Inspect the target repository's AGENTS.md and existing conventions. Read LOCAL_AI_API_KEY from its local ignored environment file or intended deployment environment. Use its own project key, never an unrelated OLLAMA_API_KEY. Implement a reusable server-side client, small prompts, schema checks, graceful failures, and meaningful tests. Report whether only local integration is complete or the actual Vercel deployment was verified. A passing local API check does not prove a Vercel function can reach the service.

## Ranked default or deliberate model choice

Use `auto` to follow the best current model for the job. A concrete installed/tested model ID is a real explicit override, not a default alias. `GET /v1/models` and `/v1/job-types` expose available alternatives. See [model policy](MODEL-POLICY.md) for the canonical selection/update contract. ClassScout’s ignored local model setting is now auto; deployed environments must set it independently when authorized.
