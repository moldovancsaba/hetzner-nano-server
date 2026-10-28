# Hungarian evaluation: no candidate passed the production gate

**Experimental API only.** Fixed gate: 20/24 strict structured checks and 5/6 usable assistant-reviewed chat replies, full completion and no OOM. No model passed it. The owner requested an API for testing/feedback; the highest-scoring complete resource-valid profile is therefore exposed as an explicitly selected experimental job, with the failed gate prominently documented. No English/image default was replaced.

| Model | Profile | Status | Structured correct | Chat usable | Gate passed |
| --- | --- | --- | --- | --- | --- |
| hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:Q3_K_M | ctx1024/batch8 | completed | 17/24 | 3/6 | False |
| qwen3:1.7b | ctx2048/batch32 | completed | 10/24 | 2/6 | False |
| granite4:1b-h | ctx2048/batch32 | completed | 10/24 | 2/6 | False |
| hungarian-qwen35-2b:q4_k_m | ctx2048/batch32 | completed | 8/24 | 1/6 | False |
| gemma3:1b | ctx2048/batch32 | completed | 5/24 | 0/6 | False |
| qwen3.5:0.8b | ctx2048/batch32 | completed | 4/24 | 1/6 | False |
| hungarian-qwen35-trimmed:q8_0 | ctx2048/batch32 | completed | 3/24 | 1/6 | False |
| hf.co/QuantFactory/EuroLLM-1.7B-Instruct-GGUF:Q4_K_M | ctx2048/batch32 | completed | 3/24 | 1/6 | False |
| hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:Q3_K_M | ctx2048/batch32 | failed | 3/24 | 0/6 | False |

## Resource result and scope

The 4B Q3 artifact first failed with OOM at context2048/batch32. A single documented changed-condition retest at context1024/batch8 completed all 30 cases with zero additional OOM kills. It uses the same frozen references. The initial resource failure is retained and is not represented as a completed language accuracy test. Eight distinct model IDs were evaluated across nine profile attempts.

JSON validity was scored separately from strict types/fields and factual correctness. Free-form chat used six frozen three-criterion rubrics and anonymized model codes; one assistant assessed them. This is not an independent native-speaker review. The test is synthetic, small and profile-tuned on the same references, with no unseen product holdout; it does not certify broad fluency or real-project reliability.

Observed problems include invented/missing fields, missing-price zero instead of null, arithmetic mistakes, source-instruction following, wrong intent and unnatural Hungarian. A schema can constrain formatting but cannot be assumed to fix meaning. No full schema-assisted quality rerun was performed; public API schema checks are integration smoke tests only.

PULI 8B ordinary quantizations exceed the current runtime allowance; the reviewed 8B Q2_K package alone was 2.96 GiB, above the 2800 MiB cap. The 7B Q2 package leaves too little space for a useful KV cache/buffers and was deferred, not reported as tested. Tiny Aya is an interesting multilingual research alternative, but its CC-BY-NC license was not adopted for these service projects. Neither was installed.

Failed temporary trimmed/2B packages were removed under the idle guard; their provenance and results remain. Only synthetic references/replies were retained, not user content. See [fixtures](fixtures.json), [raw results](results.json), [chat review](chat-review.json), [rankings](rankings.json), [conversion audit](conversion.json), [4B source](fallback4b-source.json), and [API guide](../../../docs/HUNGARIAN.md).

## API verification

The independent Hungarian job is explicitly marked experimental. All 28 public API checks passed, covering project permissions, 1024-context/batch8 profile, a schema-constrained integration example, result deletion, input-size refusal and preservation of the English default. These checks prove integration, not improved linguistic accuracy. A cleanup race initially removed the temporary artifact between testing and activation; exact tested weights were restored under the new default policy, and deployment now verifies installed digests before applying source changes.
