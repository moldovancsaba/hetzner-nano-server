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
