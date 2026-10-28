# Hungarian text evaluation, round 1

Independent Hungarian workstream. English, recognition, moderation, movies and Hungarian OCR scores are unchanged.

The frozen synthetic set contains 24 structured Hungarian cases plus six separately reviewed short conversational tasks. Expected values never enter model prompts or schemas. Cases cover accents, morphology, numbers, negation, intent, grounded catalogue filtering, missing facts, dates, arithmetic, source-instruction resistance and consent. They are narrow synthetic evaluation references, not representative production or training data.

Candidates: Granite 4 1B Hybrid (English control), Qwen 3 1.7B, Gemma 3 1B, EuroLLM 1.7B, Qwen 3.5 0.8B, and the Hungarian-vocabulary-trimmed Qwen 3.5 artifact. Previously weak Hungarian results are not rerun unchanged: this is a new frozen Hungarian-only dataset and explicit native non-thinking profile, with strict scoring and separate conversation review.

## Conversion and execution

The trimmed upstream revision is pinned in conversion.json. Convert in an isolated local environment using official llama.cpp revision 5d7793d6fcce4eb4b11ab5be856dfa4e4c8fde9b and standard safetensors. No model-provided Python or trust_remote_code runs. The tokenizer vocabulary reindex changes llama.cpp's token-ID fingerprint; pre-tokenizer, normalizer, decoder and post-processor were checked identical to upstream Qwen 3.5 before adding the exact known fingerprint. All 473 source tensors had finite values. Model weights and local dependency environments are excluded from public Git.

Run build_fixtures.py before inference. Stage run.py, plan.json and fixtures.json in /opt/narimato-benchmarks/hu-round1. The runner reuses the existing Round 4 bounded inference/memory helpers and uses a renewable idle gateway lease for each native call, giving production work opportunities between cases. Cleanup pauses and resumes in finally. All models use 2048 context, batch 32, temperature zero, explicit non-thinking and 192 output tokens. No memory cap increase or swap. Existing default text is restored afterward.

Expected fields are checked with exact JSON types, including booleans versus integers and missing values versus fabricated zero. Free-form replies are reviewed against the frozen three-point criteria by the assistant, not a second independent Hungarian-speaking human. A production fluency certificate cannot be inferred from this pilot. Acceptance thresholds are fixed in fixtures.json and reported even if no candidate meets them.

See results.json, chat-review.json, rankings.json, REPORT.md, conversion.json and the API guide after publication. Benchmark responses contain only authored synthetic tasks. No client content, keys or live customer data are used.
