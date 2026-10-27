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

