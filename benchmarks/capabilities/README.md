# Capability and model-switch benchmark

Owner-requested 2026-10-26: compare small models for ClassScout Atlas listing recommendation, OpenStreetMap venue lookup, and image analysis, including valid output formats and unload/load latency.

## Reproduce

1. `node fetch-listings.cjs` on the owner’s Mac makes a read-only, projected, indexed query to Atlas using ClassScout’s existing ignored .env.local. It reads at most eight public serving records. Credentials are never copied to the model host or saved in results.
2. OSM input is a single cached Nominatim response for Bronx Zoo, New York. `osm.json` records source URL, attribution and policy. Do not refetch per model. Public Nominatim policy requires identifying requests, at most 1/sec, caching, attribution, no autocomplete or systematic scraping, and no private data. https://operations.osmfoundation.org/policies/nominatim/
3. `cats.png` was downloaded from https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/coco_sample.png and visually inspected: two cats on a pink couch/blanket with two remote controls. It is a controlled photo fixture, not a representative image dataset.
4. Pull the candidate tags through SSH (not public management APIs). The main run uses the existing 2-CPU/2800-MiB cap and 2048 context.
5. Copy run.py, listings.json, osm.json and cats.png to /opt/narimato-ai/benchmark/. Run `python3 /opt/narimato-ai/benchmark/run.py` on the server. Outputs update results.json after every case. The script restores qwen3:1.7b in finally on ordinary termination; SIGKILL/host failure still requires manual recovery.
6. Copy results.json locally; read REPORT.md. Never silently discard failed or timed-out cases.

## Design and limits

Two trials per text case, deterministic temperature zero, native JSON constraint enabled. Seven text cases: Bronx soccer recommendation; Brooklyn swimming recommendation; no matching skiing listing; unknown-price exclusion; constrained filter plan; OSM coordinates/website/missing ticket price; ignore malicious source text. A separate native function-call test checks real tool-call arguments rather than merely claiming tool capability. The model never receives arbitrary database execution privileges.

Two explicit unload/reload trials per candidate record unload request time, first reply time, and Ollama load_duration. Files are downloaded and Linux filesystem caching is uncontrolled; these are model-cold, not guaranteed OS-cold disk tests. Trial one switches from the previous model; trial two reloads the same model. Unload endpoint response time is not a precise measure of physical RAM reclamation. One loaded-model limit remains in place.

Vision test uses a vision-capable model identified by /api/show capabilities. It requests description, cat count, and structured JSON twice. Text-only model tags are recorded as ineligible for images rather than falsely scored as successful vision. No current image-upload feature is added to Pandora by this benchmark.

Memory is cgroup memory.current sampled every 200 ms, including cache and container overhead, not just model RSS. Small samples and shared CPU make latency descriptive, not an SLA. Concurrent personal/API use can perturb results. Two deterministic repetitions of a case are not independent quality examples.

Actual Atlas network access here originates on the Mac. A backend tool fetches the public listing subset and the model on Hetzner ranks it. Hetzner-to-Atlas network allowlisting is not verified. OSM access is likewise an application lookup with cached facts passed to the model, not autonomous browsing. Production integration into ClassScout/Pandora remains separate work.

## Sources

- https://ollama.com/library/qwen3:0.6b
- https://ollama.com/library/qwen3:1.7b
- https://ollama.com/library/qwen2.5:1.5b
- https://ollama.com/library/gemma3:1b
- https://ollama.com/library/llama3.2:1b
- https://ollama.com/library/smollm2:1.7b
- https://ollama.com/library/moondream
- https://operations.osmfoundation.org/policies/nominatim/
