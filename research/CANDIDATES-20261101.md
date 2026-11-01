# Follow-up shortlist — 2026-11-01

This review follows the owner's request to continue full testing. Pinned metadata is in `candidates-20261101-metadata.json`. The Hugging Face connector was unavailable; metadata and cards were read directly from the official Hub. Publisher claims are not benchmark results.

| Candidate | Evidence and constraints | Decision |
| --- | --- | --- |
| [Marqo NSFW 384](https://huggingface.co/Marqo/nsfw-image-detection-384) | Apache-2.0; 5,597,762 parameters; 22,404,720-byte safetensors. Standard timm tiny ViT, fixed 384 input, labels **NSFW index 0 / SFW index 1**. Original weights and exported ONNX agree on all 41 existing research images; preprocessing separately matches timm on all 41. | Test binary nudity/sexual-content union at precommitted threshold 0.5. Separate cohort, not nine-category rank. Requires held-out calibration before product use. |
| [Google SigLIP 2 base 224](https://huggingface.co/google/siglip2-base-patch16-224) | Apache-2.0; 375M parameters; 1.50 GB FP32 safetensors for image+text encoders. Zero-shot label matching, not a dedicated prohibited-content detector. CPU/framework overhead and label-prompt sensitivity require an isolated resource preflight. | Metadata-only reserve candidate. Not downloaded or tested in this continuation. |
| [NYTK PULI GPTrio](https://huggingface.co/NYTK/PULI-GPTrio) | Hungarian model; 7.67B parameters, about 15.35 GB FP16 across four safetensors; published **CC-BY-NC-4.0**. A base language-model tag is not instruction-following approval. | Does not fit this commercial CPU service's practical memory/licence requirements. No download. |
| [SambaLingo Hungarian Chat](https://huggingface.co/sambanovasystems/SambaLingo-Hungarian-Chat) | Hungarian chat model; 6.95B parameters, about 13.89 GB BF16; Llama 2 terms. A useful quantization plus context is beyond the current 2800 MiB native cap. | Candidate for a separately authorized larger-host comparison, not the current 4 GB host. No download or external inference. |
| [Helsinki English→Hungarian OPUS-MT](https://huggingface.co/Helsinki-NLP/opus-mt-en-hu) | Apache-2.0 translation task. Could translate controlled English responses, but adds semantic drift and is not a Hungarian chat model. | Translation-only reserve; needs a distinct bidirectional faithfulness evaluation. No routing change. |

A direct metadata request for `KoalaAI/NSFW_Detection` failed. Availability and artifact identity are unverified; do not treat it as an accessible candidate or infer its current licence.

Hungarian remains separate from English. Existing Qwen experimental results and the failed Phi-4 Mini memory test are unchanged. A new small-model name or advertised context length does not establish better Hungarian role following or grounding.

Camera has twelve human-reviewed rejection reasons. Marqo can only contribute to nudity/sexual-content evidence; zero-shot labels do not prove detection of political content, competitor brands, project-specific forbidden content, spam, quality or `other`. A reviewed 1/2/3-model union must be validated on a fresh held-out split before API promotion. Live Camera images and conversations remain excluded from training and benchmark storage.
