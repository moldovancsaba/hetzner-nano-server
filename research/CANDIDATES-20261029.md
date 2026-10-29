# Reviewed candidates — 2026-10-29

Four previously untested checkpoints selected for full relevant suites on the existing CAX11. Exact files, revisions, source licenses and SHA-256 values are frozen in [Round 6 metadata](../benchmarks/round6/source-metadata.json). One package is staged at a time, preserving a 4 GiB disk floor and the existing 2800 MiB native cap.

| Candidate | Primary weights | Additional image projector budget | Reason to test |
| --- | --- | --- | --- |
| [LFM2 1.2B Q4](https://huggingface.co/LiquidAI/LFM2-1.2B-GGUF) | 731 MB | none | New checkpoint distinct from tested LFM2.5; low resource budget and source-grounded extraction |
| [OLMo 2 0425 1B Instruct Q4](https://huggingface.co/allenai/OLMo-2-0425-1B-Instruct-GGUF) | 936 MB | none | Different open instruction-tuned family, native tools and JSON correctness |
| [SmolVLM2 256M Video Q8](https://huggingface.co/ggml-org/SmolVLM2-256M-Video-Instruct-GGUF) | 175 MB | <=190 MB | New tiny vision checkpoint distinct from SmolVLM 256M and tested 500M Video; still-image tests only |
| [InternVL3.5 1B Q4](https://huggingface.co/bartowski/OpenGVLab_InternVL3_5-1B-GGUF) | 484 MB | <=623 MB | New compact general vision/OCR family; verify real Ollama compatibility |

These are artifact sizes, not total working-memory estimates. Publisher metadata does not prove accuracy or usable context. The LFM source includes a separate HIP-optimized Q4 file; the exact standard Q4 filename is selected explicitly, rather than assuming a quantization tag disambiguates it. Runtime inference uses existing Ollama code, with no model-provided Python execution.

Hungarian is evaluated independently on the same complete frozen suite, not inferred from English scores. Neither text candidate is presented as a Hungarian specialist. The discovered `ikhou/dict-xs` is a word/phrase dictionary model, so its Hungarian tag is not a reason to install it as a conversational coaching replacement. Larger Phi/PULI candidates remain subject to honest disk/memory preflight rather than violating the existing floor or deleting protected client-used weights.

See [Round 6 protocol and results](../benchmarks/round6/README.md). No movie capability, universal moderation clearance or complete twelve-reason coverage is inferred.
