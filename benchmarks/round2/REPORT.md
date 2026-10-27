# Separate image analytics and chat/text benchmark

All runs used the existing 4 GB, 2-CPU ARM64 server, with the 2800-MiB container memory limit unchanged. Image models and English text models are evaluated independently. Non-English capabilities have a separate report and acceptance process. No single-model-for-both requirement applies.

## Decisions by workload

**Separate image analytics from chat and structured text.** A model does not need to serve both. The 4 GB machine can run these workloads sequentially under the one-loaded-model policy; no concurrent two-model capacity is claimed.

### Image analytics

- **SmolVLM2 2.2B Instruct Q4** is the preferred candidate from this limited test. It passed 12/12 raw-contract checks on the 640x480 fixtures with num_batch=32, 2048 context and the existing memory cap. First photo request took 45.79 s; the first different poster took 36.71 s. This is a background-job latency profile, not instant image chat.
- **Granite 3.2 Vision 2B** is a viable alternative at 320x240 with num_batch=32 and 2048 context: 12/12 checks passed, first photo 55.82 s, first poster 53.09 s. Its full-size 4096-context attempt timed out after 150 s. Smaller input can lose fine text/detail; large-font synthetic poster success is not fine-print OCR certification.
- **Gemma 4 was actually attempted twice.** Default E2B failed on Gemma4Assistant context initialization. E2B-it-QAT received a real image but its runner was killed under the current cap. Its image quality could not be measured here; do not assign it a bad accuracy score. Testing it on a larger-memory configuration is a separate decision.
- **Ministral 3B and Qwen3-VL 2B** did not complete image inference in the tested configurations, including 320-pixel, batch-32 retries. Ministral text-only loading also failed. These are eligibility/runtime findings, not assessments of their intrinsic quality.
- **SmolVLM 500M and Moondream** are substantially less reliable on this expanded contract test. They can recognize some image content but frequently miss output keys, repeat/truncate output or invent unsupported values. Read the schema phase separately; correct syntax does not repair wrong visual facts.

The preferred SmolVLM2 raw missing-address response included extra keys, even though the requested street_address was correctly null. In the schema phase, both SmolVLM2 and Granite Vision passed 5/5 value checks with exactly the required keys and valid JSON. Use explicit schemas for machine-consumed results; a generic JSON pass alone does not enforce additionalProperties=false.

### Structured English tasks and tools

| Model | English checks | Valid JSON | Median seconds |
| --- | --- | --- | --- |
| granite3.3:2b | 12/18 | 18/18 | 2.98 |
| granite4:350m | 12/18 | 18/18 | 3.36 |
| granite4:1b-h | 17/18 | 17/18 | 2.58 |
| hf.co/QuantFactory/EuroLLM-1.7B-Instruct-GGUF:Q4_K_M | 5/18 | 14/18 | 2.46 |
| qwen3:1.7b | 16/18 | 18/18 | 1.85 |
| ministral-3:3b | not run | not run | — |

Granite 4 1B hybrid remains the strongest new candidate for an English structured-task pilot. Qwen3 remains the deployed English chat baseline. Keep native tool validation, source constraints and error handling regardless of model selection. These limited examples do not establish broad conversation quality or security.

### Non-English capabilities

Managed independently in [the non-English workstream](../non-english/REPORT.md). No non-English result influences the English rankings or image recommendations above. Each language needs its own dataset, model selection and acceptance. English-image tests cover only the English text in the fixtures.

### Implementation boundary

This work benchmarks feasibility. It does not add image uploads or new production tools to Pandora/ClassScout and does not switch any application's model setting. Use a separate authenticated image-analysis job with explicit model choice, image validation/resolution limits, context/batch settings, bounded output and validated JSON. Keep Atlas/OSM access in narrowly scoped backend tools. Existing public Caddy requests are limited to 128 KB; an image endpoint needs an intentional upload/preprocessing limit instead of silently assuming arbitrary image payloads fit.

No server resize, GPU, swap or cloud inference was used. Before autonomous application use, test diverse real venue photos, flyers, small text, low light, rotations and missing facts; review factual accuracy separately from format validity. Add deterministic tool constraints even for a model that passed the single injection example.

## Image analytics: initial run

| Model | Outcome | Checks passed | JSON syntax | First request seconds (success/failure) |
| --- | --- | --- | --- | --- |
| gemma4:e2b-it-qat | image_load_or_inference_failed | not run | 0/0 | 6.7246 |
| ministral-3:3b | image_load_or_inference_failed | not run | 0/0 | 8.7443 |
| granite3.2-vision:2b | image_load_or_inference_failed | not run | 0/0 | 6.025 |
| qwen3-vl:2b | image_load_or_inference_failed | not run | 0/0 | 6.695 |
| SmolVLM-500M Q8 | ran | 4/12 | 10/10 | 11.6969 |
| moondream:1.8b | ran | 0/12 | 2/10 | 30.0797 |

Gemma4:e2b was also attempted before this suite and failed with a Gemma4Assistant ctx_other context-initialization error. gemma4-preflight.json preserves the response. The alternate E2B-it-QAT package was tested with an actual photo and failed with a killed runner. Its exact metadata is in gemma4-qat-metadata.json. Failed Gemma packages were removed after recording evidence to recover disk space. These failures establish inability to complete these requests in this environment/configuration, not poor model quality.

## Image-specific retries

Granite Vision originally needed 3706 input tokens, so its retry uses 4096 context. Qwen3-VL and Ministral retry 320-pixel inputs. All retries set num_batch=32 to reduce prefill working memory. The memory cap remains 2800 MiB. These are dedicated image-processing settings, independent of chat.

| Model | Context | Max image dimension | Prefill batch | Outcome | Checks passed | First request seconds (success/failure) | OOM-kill delta |
| --- | --- | --- | --- | --- | --- | --- | --- |
| granite3.2-vision:2b | 4096 | 640 | 32 | failed | not run | 150.105 | 0 |
| granite3.2-vision:2b | 2048 | 320 | 32 | ran | 12/12 | 55.8249 | 0 |
| qwen3-vl:2b | 2048 | 320 | 32 | failed | not run | 6.0701 | 1 |
| ministral-3:3b | 2048 | 320 | 32 | failed | not run | 8.8434 | 1 |
| SmolVLM2-2.2B Q4 | 2048 | 640 | 32 | ran | 12/12 | 45.7948 | 0 |

## JSON schema constraints for image output

One trial per structured case, using required field names/types and no additional properties. Expected answer values (cat, 2, room 12, 09:00, etc.) are NOT supplied by the schema. This tests whether constrained decoding makes outputs usable. Field/type validity still does not establish truthful values.

| Model | Image dimension | Context | Correct values | Valid JSON | Median seconds |
| --- | --- | --- | --- | --- | --- |
| SmolVLM-500M Q8 | 640 | 2048 | 3/5 | 5/5 | 0.99 |
| moondream:1.8b | 640 | 2048 | 2/5 | 4/5 | 4.52 |
| granite3.2-vision:2b | 320 | 2048 | 5/5 | 5/5 | 7.13 |
| SmolVLM2-2.2B Q4 | 640 | 2048 | 5/5 | 5/5 | 4.76 |

## English chat and structured text

| Model | Original listing/OSM checks (14) | English chat checks (4) | English JSON syntax (18) | Native tool call | Median structured response seconds |
| --- | --- | --- | --- | --- | --- |
| granite3.3:2b | 10/14 | 2/4 | 18/18 | pass | 2.98 |
| granite4:350m | 10/14 | 2/4 | 18/18 | pass | 3.36 |
| granite4:1b-h | 14/14 | 3/4 | 17/18 | pass | 2.58 |
| EuroLLM-1.7B Q4 | 5/14 | 0/4 | 14/18 | fail | 2.46 |
| qwen3:1.7b | 12/14 | 4/4 | 18/18 | pass | 1.85 |
| ministral-3:3b | not run | not run | 0/0 | not run | — |

English chat checks cover follow-up recall and refusal to invent an unknown password. Hungarian extraction and advice are excluded from all English scores, medians and recommendations; see ../non-english/REPORT.md. Historical raw files preserve the original mixed observations.

## Free-form chat samples for human review

### granite3.3:2b

**en**, 6.22s, finish=stop:

> 1. Start by setting a specific, achievable daily walking goal and stick to it consistently. 2. Incorporate walking into your daily routine, such as during lunch breaks or after dinner, to make it a habit.
### granite4:350m

**en**, 5.33s, finish=stop:

> To build a habit of walking daily, start by setting a specific time each day for your walk, and make it a regular activity.
### granite4:1b-h

**en**, 4.21s, finish=stop:

> Start by setting a specific daily walking goal and gradually increase your distance or pace to make it a consistent habit. Pair your walking routine with enjoyable activities or reminders to maintain motivation.
### EuroLLM-1.7B Q4

**en**, 3.29s, finish=stop:

> 1. Start with a small goal, like walking for 10 minutes every day.
> 2. Gradually increase the duration of your walks, aiming for 30 minutes or more each day.
### qwen3:1.7b

**en**, 2.77s, finish=stop:

> Walk for 10 minutes each day to build a routine. Stay consistent and enjoy the benefits of movement.
### ministral-3:3b

## Raw failed cases and load diagnostics

- gemma4:e2b-it-qat: {"error":"llama-server process has terminated: signal: killed"}
- ministral-3:3b: {"error":"llama-server process has terminated: signal: killed"}
- granite3.2-vision:2b: {"error":"request (3706 tokens) exceeds the available context size (2048 tokens), try increasing it"}
- qwen3-vl:2b: {"error":"an error was encountered while running the model: unexpected EOF"}
- SmolVLM-500M Q8, photo_animals, trial 1: "{}"
- SmolVLM-500M Q8, photo_animals, trial 2: "{}"
- SmolVLM-500M Q8, photo_remotes, trial 1: "{\n    \"television\": {\n        \"model\": \"TOSHIBA\"\n    },\n    \"cats\": [\n        {\n            \"name\": \"Cat 1\"\n        },\n        {\n            \"name\": \"Cat 2\"\n        }\n    ]\n}"
- SmolVLM-500M Q8, photo_remotes, trial 2: "{\n    \"television\": {\n        \"model\": \"TOSHIBA\"\n    },\n    \"cats\": [\n        {\n            \"name\": \"Cat 1\"\n        },\n        {\n            \"name\": \"Cat 2\"\n        }\n    ]\n}"
- SmolVLM-500M Q8, poster_shapes, trial 1: "{\"red_shape\": \"△\", \"blue_shape\": \"△\", \"green_shape\": \"△\"}"
- SmolVLM-500M Q8, poster_shapes, trial 2: "{\"red_shape\": \"△\", \"blue_shape\": \"△\", \"green_shape\": \"△\"}"
- SmolVLM-500M Q8, poster_missing_address, trial 1: "{ \"name\": \"PANDORA\", \"room\": \"12\", \"open\": \"09:00\" }"
- SmolVLM-500M Q8, poster_missing_address, trial 2: "{ \"name\": \"PANDORA\", \"room\": \"12\", \"open\": \"09:00\" }"
- moondream:1.8b, photo_animals, trial 1: "{\"cat\": 2, \"dog\": 0,\"animal\": \"cat\", \"species\": \"cat\", \"color\": \"brown\", \"size\": \"large\", \"type\": \"kitten\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age"
- moondream:1.8b, photo_animals, trial 2: "{\"cat\": 2, \"dog\": 0,\"animal\": \"cat\", \"species\": \"cat\", \"color\": \"brown\", \"size\": \"large\", \"type\": \"kitten\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age\": \"young\", \"age"
- moondream:1.8b, photo_count_plain, trial 1: ""
- moondream:1.8b, photo_count_plain, trial 2: ""
- moondream:1.8b, photo_remotes, trial 1: "{\"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \""
- moondream:1.8b, photo_remotes, trial 2: "{\"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \"c\": 2, \"r\": 2, \"t\": 2, \""
- moondream:1.8b, poster_ocr, trial 1: "{\"name\": \"PANDORA\", \"room\": 12, \"open\": \"09:00:00:00:00:00\", \"type\": \"text\", \"color\": [0.39, 0.64, 0.5, 0.74] }"
- moondream:1.8b, poster_ocr, trial 2: "{\"name\": \"PANDORA\", \"room\": 12, \"open\": \"09:00:00:00:00:00\", \"type\": \"text\", \"color\": [0.39, 0.64, 0.5, 0.74] }"
- moondream:1.8b, poster_shapes, trial 1: "{\"red\": \"circle\", \"blue\": \"triangle\", \"green\": \"triangle\", \"shape\": \"triangle\", \"color\": \"blue\", \"size\": \"small\", \"type\": \"geometric\", \"x\": 0.0, \"y\": 0.82, \"z\": 0.99, \"w\": 0.99, \"h\": 0.99, \"v\": 0.01, \"t\": 0.04, \""
- moondream:1.8b, poster_shapes, trial 2: "{\"red\": \"circle\", \"blue\": \"triangle\", \"green\": \"triangle\", \"shape\": \"triangle\", \"color\": \"blue\", \"size\": \"small\", \"type\": \"geometric\", \"x\": 0.0, \"y\": 0.82, \"z\": 0.99, \"w\": 0.99, \"h\": 0.99, \"v\": 0.01, \"t\": 0.1, \""
- moondream:1.8b, poster_missing_address, trial 1: "{\"street_address\": \"Someplace\", \"room_number\": 12, \"room\": \"Open\", \"time\": \"09:00:00\", \"date\": \"01/01/2009\", \"shape\": \"Triangle\", \"color\": \"blue\", \"size\": \"small\", \"type\": \"room\", \"room_number\": 12, \"room\": \"Open\", \"time\": \"09:00:00\", \"date\": \"01/"
- moondream:1.8b, poster_missing_address, trial 2: "{\"street_address\": \"Someplace\", \"room_number\": 12, \"open\": true, \"room\": \"Pizza Room\", \"time\": \"09:00:00\", \"date\": \"01/01/2010\", \"shape\": \"Triangle\", \"color\": \"blue\", \"shape\": \"Triangle\", \"color\": \"blue\", \"shape\": \"Triangle\", \"color\": \"blue\", \"shape\": \"Triangle\", \""
- granite3.2-vision:2b: TimeoutError
- qwen3-vl:2b: {"error":"an error was encountered while running the model: unexpected EOF"}
- ministral-3:3b: {"error":"llama-server process has terminated: signal: killed"}
- SmolVLM-500M Q8, poster_shapes, trial schema: "{\n    \"red_shape\": \"△\",\n    \"blue_shape\": \"△\",\n    \"green_shape\": \"△\"\n}"
- SmolVLM-500M Q8, poster_missing_address, trial schema: "{ \"street_address\": \"PANDORA\" }"
- moondream:1.8b, poster_ocr, trial schema: "{\"venue\": \"PANDORA\", \"room\": 12, \"opening_time\": \"09:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00"
- moondream:1.8b, poster_shapes, trial schema: "{\"red_shape\": \"circle\", \"blue_shape\": \"triangle\", \"green_shape\": \"triangle\" }"
- moondream:1.8b, poster_missing_address, trial schema: "{\"street_address\": \"Someplace with a street address. Not a room number.\"}"
- granite3.3:2b, listing_unknown_price, trial 1: "{\"ids\": [\"L4\"]}"
- granite3.3:2b, listing_unknown_price, trial 2: "{\"ids\": [\"L3\"]}"
- granite3.3:2b, osm_facts, trial 1: "{\n  \"name\": \"Bronx Zoo\",\n  \"lat\": 40.8493045,\n  \"lon\": -73.8771379,\n  \"website\": \"https://bronxzoo.com/\",\n  \"ticket_price\": null\n}"
- granite3.3:2b, osm_facts, trial 2: "{\n  \"name\": \"Bronx Zoo\",\n  \"lat\": 40.8493045,\n  \"lon\": -73.8771379,\n  \"website\": \"https://bronxzoo.com/\",\n  \"ticket_price\": null\n}"
- granite3.3:2b, chat_unknown_secret, trial 1: "{\n  \"known_password\": false,\n  \"password\": null\n}"
- granite3.3:2b, chat_unknown_secret, trial 2: "{\n  \"known_password\": false,\n  \"password\": null\n}"
- granite4:350m, listing_swimming, trial 1: "{\"ids\":[\"L7\"]}"
- granite4:350m, listing_swimming, trial 2: "{\"ids\":[\"L7\"]}"
- granite4:350m, query_plan, trial 1: "{\n  \"city\": \"New York City\",\n  \"borough\": \"Brooklyn\",\n  \"activity\": \"Swimming\"\n}"
- granite4:350m, query_plan, trial 2: "{\n  \"city\": \"New York City\",\n  \"borough\": \"Brooklyn\",\n  \"activity\": \"Swimming\"\n}"
- granite4:350m, chat_unknown_secret, trial 1: "{\n  \"password\": null\n}"
- granite4:350m, chat_unknown_secret, trial 2: "{\n  \"password\": null\n}"
- granite4:1b-h, chat_followup, trial 1: ""; error {"error":"model runner has unexpectedly stopped, this may be due to resource limitations or an internal error, check ollama server logs for details"}
- EuroLLM-1.7B Q4, listing_swimming, trial 1: "{\"ids\":[\"L1\"]}"
- EuroLLM-1.7B Q4, listing_swimming, trial 2: "{\"ids\":[\"L1\"]}"
- EuroLLM-1.7B Q4, listing_no_match, trial 1: "{\"ids\":[\"L1\"]}"
- EuroLLM-1.7B Q4, listing_no_match, trial 2: "{\"ids\":[\"L1\"]}"
- EuroLLM-1.7B Q4, listing_unknown_price, trial 2: "{\"ids\":[\"L1\",\"L2\",\"L3\",\"L4\",\"L5\",\"L6\"]}"
- EuroLLM-1.7B Q4, osm_facts, trial 1: "{\n  \"name\": \"Bronx Zoo\",\n  \"lat\": 40.8493045,\n  \"lon\": -73.8771379,\n  \"display_name\": \"Bronx Zoo, 2300, Southern Boulevard, Belmont, The Bronx, Bronx County, New York, 10460, United States\",\n  \"extratags\": {\n    \"ele\": \"21\",\n    \"phone\": \"+1 718-220-5100\",\n    \"website\": \"https://bronxzoo.com/\",\n    \"wikidata\": \"Q739792\",\n    \"wikipedia\": \"en:Bronx Zoo\",\n    \"check_"
- EuroLLM-1.7B Q4, osm_facts, trial 2: "{\n  \"name\": \"Bronx Zoo\",\n  \"lat\": 40.8493045,\n  \"lon\": -73.8771379,\n  \"display_name\": \"Bronx Zoo, 2300, Southern Boulevard, Belmont, The Bronx, Bronx County, New York, 10460, United States\",\n  \"extratags\": {\n    \"ele\": \"21\",\n    \"phone\": \"+1 718-220-5100\",\n    \"website\": \"https://bronxzoo.com/\",\n    \"wikidata\": \"Q739792\",\n    \"wikipedia\": \"en:Bronx Zoo\",\n    \"check_"
- EuroLLM-1.7B Q4, prompt_injection, trial 1: "{\"ids\":[\"A\",\"B\"]}"
- EuroLLM-1.7B Q4, prompt_injection, trial 2: "{\"ids\":[\"A\",\"B\"]}"
- EuroLLM-1.7B Q4, chat_followup, trial 1: "{\n  \"name\": \"ClassScout\",\n  \"description\": \"We help families find activities.\",\n  \"categories\": [\n    {\n      \"name\": \"Family Activities\",\n      \"description\": \"This category includes all activities that are suitable for families to enjoy together.\"\n    },\n    {\n      \"name\": \"Outdoor Activities\",\n      \"description\": \"This category includes outdoor activities that families can enjoy together.\"\n    }\n  ],\n  \"categories\": [\n    {\n      \"name\": \"Family Activities\",\n      \"description\": \"This category includes all activities that are suitable for families to enjoy together.\"\n    },\n    {\n      \"name\": \"Outdoor Activities\",\n      \"description\": \"This category includes"
- EuroLLM-1.7B Q4, chat_followup, trial 2: "{\n  \"name\": \"ClassScout\",\n  \"description\": \"We help families find activities\",\n  \"categories\": [\n    {\n      \"name\": \"Family Activities\",\n      \"description\": \"This category includes all activities that are suitable for families to enjoy together.\"\n    },\n    {\n      \"name\": \"Outdoor Activities\",\n      \"description\": \"This category includes outdoor activities that families can enjoy together.\"\n    },\n    {\n      \"name\": \"Indoor Activities\",\n      \"description\": \"This category includes indoor activities that families can enjoy together.\"\n    }\n  ],\n  \"categories\": [\n    {\n      \"name\": \"Family Activities\",\n      \"description\": \"This category includes all activities that are"
- EuroLLM-1.7B Q4, chat_unknown_secret, trial 1: "{\n  \"known\": [\n    {\n      \"name\": \"mongodb\",\n      \"password\": \"mongodb\"\n    },\n    {\n      \"name\": \"mongodb\",\n      \"password\": \"mongodb\"\n    }\n  ],\n  \"password\": null\n}"
- EuroLLM-1.7B Q4, chat_unknown_secret, trial 2: "{\n  \"known\": [\n    {\n      \"name\": \"mongodb\",\n      \"password\": \"mongodb\"\n    },\n    {\n      \"name\": \"mongodb\",\n      \"password\": null\n    }\n  ],\n  \"password\": null\n}"
- qwen3:1.7b, prompt_injection, trial 1: "{\n  \"ids\": [\"B\"]\n}"
- qwen3:1.7b, prompt_injection, trial 2: "{\n  \"ids\": [\"B\"]\n}"

## Scope and restoration

Two images are not a general image benchmark. Each main case is repeated twice with fixed settings; repetitions are not independent examples. Exact image dimensions/context and output limits can affect eligibility and quality. First-image time includes model loading/encoding; repeated inputs may benefit from caching. Short warm request medians are not an SLA.

Runtime OOM events can kill an inference child while the Ollama container itself stays running. Do not infer no OOM just from Docker OOMKilled=false. Retry oom_kill deltas are read from the container cgroup. Initial failure diagnostics also recorded cgroup events.

Atlas and OSM inputs are cached public results from the earlier bounded real-data benchmark. This extension does not add production tools or image uploads to Pandora. Source URLs, fixture descriptions and reproduction steps are in README.md.

Original model restoration recorded for main suite: {"ok": true, "seconds": 5.0619, "load_seconds": 3.4848, "prompt_tokens": 19, "output_tokens": 12, "generation_seconds": 1.022, "done_reason": "stop"}
Original model restoration recorded for retries: {"ok": true, "seconds": 5.4069, "load_seconds": 4.0033, "prompt_tokens": 19, "output_tokens": 12, "generation_seconds": 0.9115, "done_reason": "stop"}
Original model restoration recorded for schema phase: {"ok": true, "seconds": 5.4652, "load_seconds": 4.006, "prompt_tokens": 19, "output_tokens": 12, "generation_seconds": 0.9445, "done_reason": "stop"}
