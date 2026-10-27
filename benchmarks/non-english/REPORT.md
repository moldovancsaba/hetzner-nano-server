# Non-English evaluation: independent workstream

Non-English performance does not affect English chat, English structured-task or English-image/OCR rankings. Select and approve a model separately for each language and use case. No combined multilingual score is used.

## Hungarian: existing preliminary evidence

Only two repeats of one constrained extraction and one free-form advice sample per loaded model exist. This is insufficient to approve Hungarian support. The extraction prompt provides the city/activity labels and mainly checks the number and output contract. Weak advice samples are a separate language finding, not a penalty on English capabilities.

| Model | Constrained extraction | Hungarian chat status |
| --- | --- | --- |
| granite3.3:2b | 2/2 | preliminary; not approved |
| granite4:350m | 0/2 | preliminary; not approved |
| granite4:1b-h | 2/2 | preliminary; not approved |
| hf.co/QuantFactory/EuroLLM-1.7B-Instruct-GGUF:Q4_K_M | 0/2 | preliminary; not approved |
| qwen3:1.7b | 2/2 | preliminary; not approved |
| ministral-3:3b | not run | not run |

## Samples (Hungarian only)

### granite3.3:2b

> 1. Napi séték küldeinek: A napi séték küldeinek, hogy küldetésre van szereznek, és ezek a sétéknek születették a napi séték küldeinek.
> 
> 2. Napi séték küldetés: A napi séték küldetésének, hogy a sétéknek szereznek, hogy kellene élvek a napi séték küldeinek, és ezek a sétéknek

### granite4:350m

> A napi sétára, a két rövid mondatban, a több számú szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szintű szint

### granite4:1b-h

> 1. Szentpéter terén a napi sétára a legjobb hely, mert a terben sok szembenézési pont van.

### hf.co/QuantFactory/EuroLLM-1.7B-Instruct-GGUF:Q4_K_M

> A napi sétára szokássá kell válnia.
> 
> A napi sétára szokássá kell válni.

### qwen3:1.7b

> Szokhatok rá a napi sétára úgy, hogy előkészületekben elvégzi a szükséges felkészülést, és a sétára után megérzi a jövőt.

## Acceptance and operation

- Keep language-specific datasets, results, latency targets and model choices here, separate from English evaluations.
- Test each requested language independently with realistic conversations and project tasks; obtain fluent human review of grammar, meaning, usefulness and factuality.
- Evaluate retrieval, generation, translation and OCR separately. English OCR results do not establish Hungarian or other-script OCR support.
- Measure format validity and task correctness separately from language fluency. Do not average languages into one approval score.
- Use an explicit language/task routing decision; do not silently use an English-approved model or switch providers when language support is unvalidated.
- Current production routing has not been changed. No non-English production capability has been approved by these tests.
- hungarian-results.json is a derived extract; original mixed raw observations remain in ../round2/ for historical reproducibility.
