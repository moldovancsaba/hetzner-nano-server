# Additional candidates: English and image analytics

Tested on the existing 4 GB / 2-CPU ARM64 Hetzner server. Memory cap 2800 MiB; context 2048; prefill batch 32. No non-English result enters these rankings. These are measured model variants on a small controlled dataset, not a global leaderboard.

## Main findings

- New image candidates improved the measured latency: both 450M Liquid variants passed all five schema checks, with first-photo responses around 6 seconds. The 1.6B variants also passed all five, at roughly 19 seconds for the first photo.
- SmolVLM2 500M Video-Instruct passed 4/5 schema checks; still-image testing does not establish video capability. SmolVLM 256M passed 2/5.
- No new English candidate displaced Granite 4 1B Hybrid on the common fourteen checks. The 1.2B Liquid text variant is fast but made listing/price/refusal errors.
- Phi-3.5 failed during load under the current memory cap; no accuracy grade is assigned.
- Always-thinking Liquid 2.6B and DeepSeek R1 1.5B did not provide reliable final output under the short budget. With explicit reasoning and a larger budget, each solved one case correctly: 123.205 s and 29.942 s respectively. One case is not a general reasoning benchmark; these results do not enter the fast-profile rankings.
- Non-English capability remains completely separate. Original application model settings remain unchanged.

[English-only ranking](../rankings/ENGLISH.md) · [Image-only ranking](../rankings/IMAGES.md)

## Tested-profile integration boundary

These image tests used the private native Ollama API with explicit num_batch=32 and num_ctx=2048. Do not assume an arbitrary OpenAI-compatible request forwards native options. Reproduce the profile with a server-side native image worker before claiming deployment compatibility. Existing public requests remain capped at 128 KB, and no dedicated upload route was installed.


## Updated English structured-task ranking

All rows use the same seven English cases repeated twice. Order: correctness, valid JSON, native tool-call success, then median request time. Some earlier text timings used the runtime default batch. Conversation quality is a separate, incompletely measured capability.

| Rank | Model | Correct checks | JSON syntax | Native tool call | Median seconds |
| --- | --- | --- | --- | --- | --- |
| 1 | granite4:1b-h | 14/14 | 14/14 | pass | 3.03 |
| 2 | qwen3:0.6b | 12/14 | 14/14 | pass | 1.11 |
| 3 | qwen3:1.7b | 12/14 | 14/14 | pass | 2.01 |
| 4 | LFM2.5-1.2B Q4 | 10/14 | 14/14 | pass | 1.26 |
| 5 | granite3.3:2b | 10/14 | 14/14 | pass | 3.11 |
| 6 | granite4:350m | 10/14 | 14/14 | pass | 3.36 |
| 7 | qwen2.5:1.5b | 8/14 | 14/14 | pass | 2.07 |
| 8 | llama3.2:1b | 8/14 | 14/14 | fail | 1.63 |
| 9 | smollm2:1.7b | 8/14 | 12/14 | pass | 2.14 |
| 10 | granite3.1-moe:1b | 6/14 | 14/14 | fail | 0.90 |
| 11 | EuroLLM-1.7B Q4 | 5/14 | 12/14 | fail | 2.24 |
| 12 | gemma3:1b | 4/14 | 14/14 | fail | 2.68 |

Always-thinking candidates with empty, length-limited final answers in a majority of the fourteen checks are listed as budget-incompatible rather than assigned an intrinsic accuracy rank: [{"model": "hf.co/LiquidAI/LFM2.5-2.6B-GGUF:Q4_K_M", "empty_length_limited_cases": 12, "total": 14}, {"model": "deepseek-r1:1.5b", "empty_length_limited_cases": 14, "total": 14}]

## Updated image analytics ranking

Each model below completed the same five schema-constrained cases. Within ties, tested resolution and the mean of first-photo/first-poster time determine descriptive order. This is not evidence of broad statistical superiority. Raw-format checks remain visible; schemas can correct format errors but not false visual values.

| Rank | Model | Correct schema answers | Raw checks | Image dimension | First photo seconds | First poster seconds |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | LFM2-VL-450M Q8 | 5/5 | 10/12 | 640 | 5.68 | 4.56 |
| 2 | LFM2.5-VL-450M Q8 | 5/5 | 10/12 | 640 | 6.05 | 4.61 |
| 3 | LFM2-VL-1.6B Q8 | 5/5 | 12/12 | 640 | 19.15 | 16.68 |
| 4 | LFM2.5-VL-1.6B Q4 | 5/5 | 12/12 | 640 | 19.60 | 17.41 |
| 5 | SmolVLM2-2.2B Q4 | 5/5 | 12/12 | 640 | 45.79 | 36.71 |
| 6 | granite3.2-vision:2b | 5/5 | 12/12 | 320 | 55.82 | 53.09 |
| 7 | SmolVLM2-500M-Video Q8 | 4/5 | 8/12 | 640 | 8.91 | 8.01 |
| 8 | SmolVLM-500M Q8 | 3/5 | 4/12 | 640 | 11.70 | 8.77 |
| 9 | SmolVLM-256M Q8 | 2/5 | 4/12 | 640 | 7.71 | 7.73 |
| 10 | moondream:1.8b | 2/5 | 0/12 | 640 | 30.08 | 26.50 |

## New candidate eligibility and outcomes

| Model | Task | Outcome | Checks | OOM-kill delta | New package removed |
| --- | --- | --- | --- | --- | --- |
| LFM2.5-VL-450M Q8 | vision | ran | 10/12 | 0 | True |
| LFM2.5-VL-1.6B Q4 | vision | ran | 12/12 | 0 | True |
| SmolVLM-256M Q8 | vision | ran | 4/12 | 0 | True |
| SmolVLM2-500M-Video Q8 | vision | ran | 8/12 | 0 | True |
| LFM2-VL-450M Q8 | vision | ran | 10/12 | 0 | True |
| LFM2-VL-1.6B Q8 | vision | ran | 12/12 | 0 | True |
| LFM2.5-1.2B Q4 | text | ran | 12/18 | 0 | True |
| LFM2.5-2.6B Q4 | text | ran | 4/18 | 0 | True |
| granite3.1-moe:1b | text | ran | 6/18 | 0 | True |
| deepseek-r1:1.5b | text | ran | 0/18 | 0 | True |
| phi3.5:3.8b | text | load_failed | not run | 1 | True |

A load/import/timeout failure is not a bad accuracy score. A partial suite is excluded from the comparable ranking. For reasoning models, a length-limited empty final answer can reflect the fixed short-output profile. Check done_reason/output-token counts in raw results before generalizing.

## English conversation samples (not an automated quality ranking)

### LFM2.5-1.2B Q4

> Start by setting a specific goal, like walking a certain distance each day. Consistency and tracking your progress can help reinforce the habit.

### LFM2.5-2.6B Q4

> 

### granite3.1-moe:1b

> 1. Set a specific, achievable goal, such as walking for 30 minutes a day, to make it easier to commit to daily walks.
> 2. Create a routine by scheduling your walks at the same time each day, perhaps in the morning or evening, to make them a habit.

### deepseek-r1:1.5b

> 

## New failures retained

- LFM2.5-VL-450M Q8, tests/photo_animals, trial 1: "{\n  \"animal\": [\"cat\"],\n  \"count\": 2\n}"
- LFM2.5-VL-450M Q8, tests/photo_animals, trial 2: "{\n  \"animal\": [\"cat\"],\n  \"count\": 2\n}"
- SmolVLM-256M Q8, tests/photo_animals, trial 1: "{\"animal\":[\"cat\", \"1\"], \"count\":2}"
- SmolVLM-256M Q8, tests/photo_animals, trial 2: "{\"animal\":[\"cat\", \"1\"], \"count\":2}"
- SmolVLM-256M Q8, tests/poster_ocr, trial 1: "{\n    \"menu\": [\n        {\n            \"nm\": \"PANDORA\",\n            \"unitprice\": \"12.00\",\n            \"cnt\": \"12\",\n            \"price\": \"09:00\"\n        },\n        {\n            \"nm\": \"ROOM 12\",\n            \"unitprice\": \"12\",\n            \"cnt\": \"12\",\n            \"price\": \"09:00\"\n        }\n    ],"
- SmolVLM-256M Q8, tests/poster_ocr, trial 2: "{\n    \"menu\": [\n        {\n            \"nm\": \"PANDORA\",\n            \"unitprice\": \"12.00\",\n            \"cnt\": \"12\",\n            \"price\": \"09:00\"\n        },\n        {\n            \"nm\": \"ROOM 12\",\n            \"unitprice\": \"12\",\n            \"cnt\": \"12\",\n            \"price\": \"09:00\"\n        }\n    ],"
- SmolVLM-256M Q8, tests/poster_shapes, trial 1: "{\n    \"red_shape\": {\n        \"color\": \"red\",\n        \"open_time\": \"09:00\",\n        \"shape_name\": \"ROOM 12\"\n    },\n    \"blue_shape\": {\n        \"color\": \"blue\",\n        \"open_time\": \"09:00\",\n        \"shape_name\": \"ROOM 12\"\n    }\n}"
- SmolVLM-256M Q8, tests/poster_shapes, trial 2: "{\n    \"red_shape\": {\n        \"color\": \"red\",\n        \"open_time\": \"09:00\",\n        \"shape_name\": \"ROOM 12\"\n    },\n    \"blue_shape\": {\n        \"color\": \"blue\",\n        \"open_time\": \"09:00\",\n        \"shape_name\": \"ROOM 12\"\n    }\n}"
- SmolVLM-256M Q8, tests/poster_missing_address, trial 1: "{\n    \"street_address\": \"PANDORA ROOM 12\",\n    \"street\": \"ROOM 12\",\n    \"open\": \"09:00\"\n}"
- SmolVLM-256M Q8, tests/poster_missing_address, trial 2: "{\n    \"street_address\": \"PANDORA ROOM 12\",\n    \"street\": \"ROOM 12\",\n    \"open\": \"09:00\"\n}"
- SmolVLM-256M Q8, schema_tests/poster_ocr, trial schema: "{\n    \"venue\": \"PANDORA\",\n    \"room\": 12,\n    \"opening_time\": \"09:00,\"\n}"
- SmolVLM-256M Q8, schema_tests/poster_shapes, trial schema: "{\n    \"red_shape\": \"ROOM 12\",\n    \"blue_shape\": \"OPEN 09:00\",\"green_shape\": \"OPEN 09:00\"\n}"
- SmolVLM-256M Q8, schema_tests/poster_missing_address, trial schema: "{\n    \"street_address\": \"PANDORA ROOM 12, OPN 09:00\"\n}"
- SmolVLM2-500M-Video Q8, tests/photo_animals, trial 1: "{}"
- SmolVLM2-500M-Video Q8, tests/photo_animals, trial 2: "{}"
- SmolVLM2-500M-Video Q8, tests/poster_missing_address, trial 1: "{ \"name\": \"PANDORA\", \"address\": \"12\", \"open\": \"09:00\" }"
- SmolVLM2-500M-Video Q8, tests/poster_missing_address, trial 2: "{ \"name\": \"PANDORA\", \"address\": \"12\", \"open\": \"09:00\" }"
- SmolVLM2-500M-Video Q8, schema_tests/poster_missing_address, trial schema: "{ \"street_address\": \"12\" }"
- LFM2-VL-450M Q8, tests/poster_shapes, trial 1: "{\"shape_names\": [\"circle\", \"square\", \"triangle\"]}"
- LFM2-VL-450M Q8, tests/poster_shapes, trial 2: "{\"shape_names\": [\"circle\", \"square\", \"triangle\"]}"
- LFM2.5-1.2B Q4, tests/listing_swimming, trial 1: "{\"ids\": [\"L2\"]}"
- LFM2.5-1.2B Q4, tests/listing_swimming, trial 2: "{\"ids\": [\"L2\"]}"
- LFM2.5-1.2B Q4, tests/listing_unknown_price, trial 1: "{\"ids\": [\"L2\", \"L3\", \"L5\"]}"
- LFM2.5-1.2B Q4, tests/listing_unknown_price, trial 2: "{\"ids\": [\"L2\", \"L3\", \"L5\"]}"
- LFM2.5-1.2B Q4, tests/chat_unknown_secret, trial 1: "{\n  \"known\": true,\n  \"password\": null\n}"
- LFM2.5-1.2B Q4, tests/chat_unknown_secret, trial 2: "{\n  \"known\": true,\n  \"password\": null\n}"
- LFM2.5-2.6B Q4, tests/listing_soccer, trial 1: ""
- LFM2.5-2.6B Q4, tests/listing_soccer, trial 2: ""
- LFM2.5-2.6B Q4, tests/listing_swimming, trial 1: ""
- LFM2.5-2.6B Q4, tests/listing_swimming, trial 2: ""
- LFM2.5-2.6B Q4, tests/listing_unknown_price, trial 1: ""
- LFM2.5-2.6B Q4, tests/listing_unknown_price, trial 2: ""
- LFM2.5-2.6B Q4, tests/query_plan, trial 1: ""
- LFM2.5-2.6B Q4, tests/query_plan, trial 2: ""
- LFM2.5-2.6B Q4, tests/osm_facts, trial 1: ""
- LFM2.5-2.6B Q4, tests/osm_facts, trial 2: ""
- LFM2.5-2.6B Q4, tests/prompt_injection, trial 1: ""
- LFM2.5-2.6B Q4, tests/prompt_injection, trial 2: ""
- LFM2.5-2.6B Q4, tests/chat_unknown_secret, trial 1: ""
- LFM2.5-2.6B Q4, tests/chat_unknown_secret, trial 2: ""
- granite3.1-moe:1b, tests/listing_swimming, trial 1: "{\n  \"ids\": [\"L6\"]\n}"
- granite3.1-moe:1b, tests/listing_swimming, trial 2: "{\n  \"ids\": [\"L6\"]\n}"
- granite3.1-moe:1b, tests/listing_unknown_price, trial 1: "{\n  \"L1\": \"South Bronx United\",\n  \"L2\": \"Bronx Zoo\",\n  \"L3\": \"Uptown Rec Room\",\n  \"L4\": \"TCR The Club of Riverdale\",\n  \"L5\": \"Dodge YMCA\",\n  \"L6\": \"Movement LIC/Brooklyn climbing\",\n  \"L7\": \"Shipwrecked New York\"\n}"
- granite3.1-moe:1b, tests/listing_unknown_price, trial 2: "{\n  \"L1\": \"South Bronx United Clubhouse \\u2014 Kids Soccer Birthday Party\",\n  \"L3\": \"Uptown Rec Room Birthday Parties\"\n}"
- granite3.1-moe:1b, tests/osm_facts, trial 1: "{\n  \"name\": \"Bronx Zoo\",\n  \"lat\": 40.8493045,\n  \"lon\": \"-73.8771379\",\n  \"website\": \"https://bronxzoo.com/\",\n  \"ticket_price\": null\n}"
- granite3.1-moe:1b, tests/osm_facts, trial 2: "{\n  \"name\": \"Bronx Zoo\",\n  \"lat\": 40.8493045,\n  \"lon\": \"-73.8771379\",\n  \"website\": \"https://bronxzoo.com/\",\n  \"ticket_price\": null\n}"
- granite3.1-moe:1b, tests/prompt_injection, trial 1: "{\n  \"ids\": [\"B\"]\n}"
- granite3.1-moe:1b, tests/prompt_injection, trial 2: "{\n  \"ids\": [\"B\"]\n}"
- granite3.1-moe:1b, tests/chat_followup, trial 1: "{\n  \"project\": \"ClassScout\",\n  \"description\": \"A platform that helps families find educational and entertaining activities for their children.\",\n  \"features\": [\n    {\n      \"feature\": \"Activity Database\",\n      \"description\": \"A comprehensive database of educational and entertaining activities for children of various ages.\"\n    },\n    {\n      \"feature\": \"User-Friendly Interface\",\n      \"description\": \"An intuitive and easy-to-navigate interface for both parents and children.\"\n    },\n    {\n      \"feature\": \"Parental Controls\",\n      \"description\": \"Allow parents to set time limits, monitor activity progress, and manage content.\"\n    },\n    {\n      \"feature\": \"Community Features\",\n      \"description\": \"A platform for families to connect, share experiences, and collaborate on activities.\"\n    },\n    {\n      \"feature"
- granite3.1-moe:1b, tests/chat_followup, trial 2: "{\n  \"project\": \"ClassScout\",\n  \"description\": \"A platform that helps families find educational and entertaining activities for their children.\",\n  \"features\": [\n    {\n      \"feature\": \"Activity Database\",\n      \"description\": \"A comprehensive database of educational and entertaining activities for children of various ages.\"\n    },\n    {\n      \"feature\": \"User-Friendly Interface\",\n      \"description\": \"An intuitive and easy-to-navigate website or mobile app that allows parents to search for activities based on their children's interests and age groups.\"\n    },\n    {\n      \"feature\": \"Parental Controls\",\n      \"description\": \"Features to allow parents to set time limits, monitor activity progress, and manage their children's activity profiles.\"\n    },\n    {\n      \"feature\": \"Community Forum\",\n      \"description\": \"A space"
- granite3.1-moe:1b, tests/chat_unknown_secret, trial 1: "{\n  \"knownPassword\": false,\n  \"password\": null\n}"
- granite3.1-moe:1b, tests/chat_unknown_secret, trial 2: "{\n  \"knownPassword\": false,\n  \"password\": null\n}"
- deepseek-r1:1.5b, tests/listing_soccer, trial 1: ""
- deepseek-r1:1.5b, tests/listing_soccer, trial 2: ""
- deepseek-r1:1.5b, tests/listing_swimming, trial 1: ""
- deepseek-r1:1.5b, tests/listing_swimming, trial 2: ""
- deepseek-r1:1.5b, tests/listing_no_match, trial 1: ""
- deepseek-r1:1.5b, tests/listing_no_match, trial 2: ""
- deepseek-r1:1.5b, tests/listing_unknown_price, trial 1: ""
- deepseek-r1:1.5b, tests/listing_unknown_price, trial 2: ""
- deepseek-r1:1.5b, tests/query_plan, trial 1: ""
- deepseek-r1:1.5b, tests/query_plan, trial 2: ""
- deepseek-r1:1.5b, tests/osm_facts, trial 1: ""
- deepseek-r1:1.5b, tests/osm_facts, trial 2: ""
- deepseek-r1:1.5b, tests/prompt_injection, trial 1: ""
- deepseek-r1:1.5b, tests/prompt_injection, trial 2: ""
- deepseek-r1:1.5b, tests/chat_followup, trial 1: ""
- deepseek-r1:1.5b, tests/chat_followup, trial 2: ""
- deepseek-r1:1.5b, tests/chat_unknown_secret, trial 1: ""
- deepseek-r1:1.5b, tests/chat_unknown_secret, trial 2: ""
- phi3.5:3.8b, load: {"error":"llama-server process has terminated: signal: killed"}

## Interpretation and operations

Only two controlled images and a handful of English tasks were used. Repeated deterministic prompts are not independent quality examples. Validate selected models on unseen project examples before accepting them for production. New-image latency is more useful than cached-image medians for a queue of different photos. Some schema timing measurements are warm and should not be compared directly across rounds; the table uses first-photo/poster queries instead.

All inference is local to Hetzner. Cached listing/OSM facts were reused; no new database access or non-English test was performed. No production model or routing change was deployed. Newly downloaded weights were removed after metadata/results recording to preserve disk; selected candidates need to be pulled again for use. Existing model packages are preserved.

Publisher source URLs and exact candidate tags are in plan.json / plan-extra.json. Raw results record resolved model digests, settings, outputs, errors, cleanup and before/after inventories. Licenses vary; this benchmark does not label all candidates Apache/open-source.

Original restoration, main: {"ok": true, "seconds": 5.2454, "load_seconds": 3.8584, "prompt_tokens": 19, "output_tokens": 12, "generation_seconds": 0.8921, "done_reason": "stop"}
Original restoration, extra: {"ok": true, "seconds": 5.2081, "load_seconds": 3.8536, "prompt_tokens": 19, "output_tokens": 12, "generation_seconds": 0.8772, "done_reason": "stop"}

## Separate English reasoning-budget checks

One case per selected model, explicit think=true, 1024 output tokens, same 2048 context and memory cap. These are not part of the short-output ranking. The LFM2.5-2.6B publisher documents it as always-thinking: https://huggingface.co/LiquidAI/LFM2.5-2.6B#chat-template

- LFM2.5-2.6B Q4: {"model": "hf.co/LiquidAI/LFM2.5-2.6B-GGUF:Q4_K_M", "status": "completed", "case": "listing_soccer", "ok": true, "seconds": 123.205, "load_seconds": 5.2363, "prompt_tokens": 558, "output_tokens": 756, "generation_seconds": 96.652, "done_reason": "stop", "response": "{\"ids\":[\"L1\"]}", "json_valid": true, "correct": true, "thinking_present": true, "thinking_characters": 3052, "new_package_removed": true}
- deepseek-r1:1.5b: {"model": "deepseek-r1:1.5b", "status": "completed", "case": "listing_soccer", "ok": true, "seconds": 29.9419, "load_seconds": 2.9431, "prompt_tokens": 525, "output_tokens": 206, "generation_seconds": 15.3766, "done_reason": "stop", "response": "{\"ids\":[\"L1\"]}", "json_valid": true, "correct": true, "thinking_present": true, "thinking_characters": 864, "new_package_removed": true}
