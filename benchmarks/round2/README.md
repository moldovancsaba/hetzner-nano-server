# Separate vision analytics and chat/text benchmark

This extension answers the owner's clarification: image analytics and chat are separate workloads. Models are evaluated per workload; no combined-model requirement is imposed.

Hardware: Hetzner CAX11, 2 shared ARM64 CPUs, 4 GB host RAM; Ollama 0.40.11, same 2800-MiB container limit. No server resize, swap allocation or GPU was added. Chat's default model/configuration is preserved.

## Inputs and scoring

Image cases use two known fixtures: the previous round's 640x480 photo of two cats and two remote controls, and poster.png, a controlled 640x480 document with text PANDORA / ROOM 12 / OPEN 09:00 plus a red circle, blue square and green triangle. poster-ground-truth.json records the exact construction. Both fixtures were visually inspected. Reduced 320-pixel copies are separate retry inputs, not silently substituted in the main test.

Six image cases repeated twice: animal identification/count in JSON, plain numeric cat count, remote count in JSON, OCR of venue/room/opening time, shape/color matching, and refusal to invent a missing street address. JSON syntax and expected fields/values are checked separately. A failed model load is recorded as untested quality, not a zero accuracy score. The first image request has its own latency; repeated images can benefit from caching.

Text/chat candidates use the same seven structured listing/OSM cases as the previous round, plus three small chat checks (follow-up recall, a constrained Hungarian extraction, and unknown-password refusal), each repeated twice. Free-form English/Hungarian habit advice is saved for human review and is not scored correct just for being nonempty. One native tool-call check tests the exact function and arguments.

The Hungarian extraction prompt supplies the target city/activity values; it primarily tests extracting the Hungarian number and following the output contract, not broad translation quality. The advice examples provide an additional qualitative language sample. Neither establishes general Hungarian proficiency.

## Candidate selection

Vision: Gemma 4 E2B (default and alternate QAT packages attempted), Ministral 3 3B, Granite 3.2 Vision 2B, Qwen3-VL 2B, SmolVLM 500M Q8, Moondream 1.8B baseline, and an additional SmolVLM2 2.2B Q4 candidate.

Text/chat: Granite 3.3 2B, Granite 4 350M, Granite 4 1B hybrid Q8, EuroLLM 1.7B Instruct Q4 (community QuantFactory conversion), Qwen3 1.7B control. Publisher identity and weights conversion are distinct; EuroLLM original is utter-project, GGUF conversion is QuantFactory.

Gemma default failed with a Gemma4Assistant ctx_other initialization error. Its alternate E2B-it-QAT package is tested with an actual image. Failed Gemma packages are removed after metadata/error preservation to recover disk space. Previously installed models are not removed. No model is downloaded or inferred through a cloud API.

## Execution

1. run.py is the main sequential benchmark. fixtures.py holds shared request helpers and cases extracted from the previous round. Place run.py, fixtures.py, cats.png, poster.png, listings.json and osm.json under /opt/narimato-ai/benchmark-round2, then run Python through SSH.
2. vision-retries.py runs after the main process completes. Granite Vision gets a 4096-token context because its original image request required 3706 tokens. Qwen3-VL and Ministral get 320-pixel inputs to test whether smaller image encoding makes them practical. The 2800-MiB memory cap is unchanged. SmolVLM2 is a new compact candidate.
3. Both scripts persist results incrementally and restore Qwen3 1.7B in finally on ordinary termination. A killed SSH/Python process still requires manual restoration and health checks.
4. Runtime errors, raw responses, durations, context and retry resolution are retained. Retry tests record cgroup oom_kill deltas around each model. Docker's OOMKilled flag alone does not establish that no inference child process was killed.

No fresh Atlas or OSM lookup is made: cached public listing/venue input is reused. No credentials are supplied to the models. This is a limited feasibility/contract benchmark, not production acceptance or independent accuracy certification. Text prompts and image fixtures do not cover real-world variability, OCR layouts, poor photos, adversarial content, or all languages.

## Sources

- https://ollama.com/library/gemma4/tags
- https://ollama.com/library/ministral-3:3b
- https://ollama.com/library/granite3.2-vision
- https://ollama.com/library/qwen3-vl:2b
- https://huggingface.co/ggml-org/SmolVLM-500M-Instruct-GGUF
- https://huggingface.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF
- https://ollama.com/library/granite3.3:2b
- https://ollama.com/library/granite4/tags
- https://huggingface.co/utter-project/EuroLLM-1.7B-Instruct
- https://huggingface.co/QuantFactory/EuroLLM-1.7B-Instruct-GGUF

OSM cached input attribution: © OpenStreetMap contributors, ODbL; policy/source recorded in osm.json. Photo source is documented in ../capabilities/README.md.

Retry requests also set num_batch=32 to reduce prefill working memory; this is a recorded request-specific configuration, not a server resize or a global default change.

## Supplemental text-only and schema phases

supplement-text.py tests Ministral 3B without any image inputs, with num_batch=32. It keeps the same 20 text/chat cases and explicit native tool call. This prevents an image inference failure from being treated as evidence that text-only use cannot work.

schema-vision.py checks five structured image cases once per operational model with a JSON schema constraining required keys/types and rejecting additional keys. Correct answer values are not embedded in the grammar. Original failures are retained; this is an explicitly different application configuration, not a replacement score.

finish-phases.py is a temporary sequential runner for this benchmark, not a recurring automation. It waits for the main results completion marker, then runs supplemental text, image-specific retries, and schema checks. Each phase restores the original model.

The schema phase also uses num_batch=32. It is an application-profile comparison against the initial defaults, not a controlled experiment isolating grammar as the only changed variable. Expected values are not hardcoded in schemas. Native output limits remain bounded; length-truncated or invalid output is retained as failure.

Schema follow-ups include the two weaker models and operational retry models. This explicitly validates stricter field contracts, including rejection of extra output keys, rather than assuming a generic JSON pass proves schema compatibility.

## Safe reproduction order

Preserve existing result files before a rerun, preferably by using a new timestamped benchmark directory. Copy the same fixtures and scripts there. Do not run two benchmark processes against the one model worker at once. A simple sequential reproduction on the server is:

```sh
python3 run.py && python3 supplement-text.py && python3 vision-retries.py && python3 schema-vision.py
```

The finish-phases.py helper was used only to continue the active run in order. Its completion-marker wait is not a fresh-run identity check: do not start it against stale completed results while a new main run is starting.

Main candidate pulls used `docker exec narimato-ollama ollama pull <exact-tag>`. Exact tags are in run.py, supplement-text.py and vision-retries.py. Gemma4:e2b and gemma4:e2b-it-qat were removed with `ollama rm` after their metadata/errors were preserved, freeing disk space. Other candidate weights remain available; no pre-existing model was removed.

## Evaluation scope correction

Non-English capability is now a completely separate workstream at ../non-english/REPORT.md. English report scores/latency exclude Hungarian extraction; only English advice appears here. Original raw JSON remains unchanged. The exact originally executed mixed runners are preserved as run-historical-mixed.py and supplement-text-historical-mixed.py. Future run.py and supplement-text.py executions exclude the Hungarian cases and sample. Non-English work needs a dedicated language-specific run and approval; do not rerun mixed scripts as the default.
