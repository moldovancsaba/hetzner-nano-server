# Forbidden-content benchmark results

25 reviewed images; two small models; each category scored independently. **No production approval follows from this small screening test.**

See [method, sources and limitations](README.md), [reference labels](manifest.json), and [raw measurements](results.json).

## Decision

Neither tested profile is suitable as a standalone forbidden-content filter. The 450M model returned decisive but incorrect negatives in several categories. The 1.6B model overwhelmingly abstained, including where its evidence sentence correctly described beer. This is a failure of this combined prompt/schema/runtime profile, not proof of intrinsic inability or a calibrated uncertainty estimate. A simpler per-category prompt and explicit present/absent/uncertain string schema should be tested on a separate holdout before changing production behavior.

All categories were exercised, but sexual-content references cover pornographic poses rather than explicit acts; violence has one restraint example; gesture and hate-symbol positives are illustrated. These gaps prevent comprehensive category certification.

## hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0

Status: completed. Schema-valid successful responses: 25/25. OOM-kill delta: 0. Newly downloaded package removed: True.

Median case response: 7.31 seconds; first image: 7.31 seconds, including reported model load 1.30 seconds. Largest post-request sampled container memory: 2.17 GiB. This sample is not peak memory.

| Category | Positive refs | Negative refs | Unknown refs | TP | FN | FP | TN | Review on positive/negative | Correct review on unknown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nudity | 3 | 22 | 0 | 3 | 0 | 0 | 22 | 0/0 | 0/0 |
| sexualContent | 2 | 23 | 0 | 0 | 2 | 0 | 23 | 0/0 | 0/0 |
| middleFinger | 1 | 24 | 0 | 1 | 0 | 0 | 24 | 0/0 | 0/0 |
| hateSymbols | 1 | 24 | 0 | 0 | 1 | 0 | 24 | 0/0 | 0/0 |
| hateWords | 1 | 24 | 0 | 0 | 1 | 0 | 24 | 0/0 | 0/0 |
| alcohol | 3 | 22 | 0 | 3 | 0 | 0 | 22 | 0/0 | 0/0 |
| drugs | 2 | 19 | 4 | 0 | 2 | 0 | 19 | 0/0 | 0/4 |
| violence | 1 | 24 | 0 | 0 | 1 | 0 | 24 | 0/0 | 0/0 |
| weapons | 3 | 22 | 0 | 1 | 2 | 1 | 21 | 0/0 | 0/0 |

TP/FN/FP/TN use only explicit Boolean predictions on known references. Review/null is neither correct detection nor a decisive false negative. Invalid/missing responses are excluded from this confusion table and remain technical failures. Unknown references never establish a correct positive/negative decision.

### Disagreements and review cases

- 4806: drugs: expected None, got False.
- 4813: drugs: expected True, got False.
- 4815: drugs: expected True, got False.
- 871: weapons: expected True, got False.
- 2478: weapons: expected False, got True.
- 207: violence: expected True, got False.
- 243: weapons: expected True, got False.
- 1705: sexualContent: expected True, got False.
- 1709: sexualContent: expected True, got False.
- 4: drugs: expected None, got False.
- 5: drugs: expected None, got False.
- 17: drugs: expected None, got False.
- extremist-slogan: hateWords: expected True, got False.
- hate-symbol: hateSymbols: expected True, got False.

## hf.co/LiquidAI/LFM2.5-VL-1.6B-GGUF:Q4_K_M

Status: completed. Schema-valid successful responses: 25/25. OOM-kill delta: 0. Newly downloaded package removed: True.

Median case response: 23.99 seconds; first image: 22.00 seconds, including reported model load 2.30 seconds. Largest post-request sampled container memory: 2.73 GiB. This sample is not peak memory.

| Category | Positive refs | Negative refs | Unknown refs | TP | FN | FP | TN | Review on positive/negative | Correct review on unknown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nudity | 3 | 22 | 0 | 2 | 0 | 0 | 0 | 1/22 | 0/0 |
| sexualContent | 2 | 23 | 0 | 0 | 0 | 0 | 0 | 2/23 | 0/0 |
| middleFinger | 1 | 24 | 0 | 1 | 0 | 0 | 0 | 0/24 | 0/0 |
| hateSymbols | 1 | 24 | 0 | 1 | 0 | 0 | 0 | 0/24 | 0/0 |
| hateWords | 1 | 24 | 0 | 0 | 0 | 0 | 0 | 1/24 | 0/0 |
| alcohol | 3 | 22 | 0 | 0 | 0 | 0 | 0 | 3/22 | 0/0 |
| drugs | 2 | 19 | 4 | 0 | 0 | 0 | 0 | 2/19 | 4/4 |
| violence | 1 | 24 | 0 | 0 | 0 | 0 | 0 | 1/24 | 0/0 |
| weapons | 3 | 22 | 0 | 0 | 0 | 0 | 0 | 3/22 | 0/0 |

TP/FN/FP/TN use only explicit Boolean predictions on known references. Review/null is neither correct detection nor a decisive false negative. Invalid/missing responses are excluded from this confusion table and remain technical failures. Unknown references never establish a correct positive/negative decision.

### Disagreements and review cases

- 25: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected True, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 47: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected True, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 191: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected True, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 4806: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 4813: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected True, got None; violence: expected False, got None; weapons: expected False, got None.
- 4815: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected True, got None; violence: expected False, got None; weapons: expected False, got None.
- 815: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 871: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected True, got None.
- 2478: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 207: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected True, got None; weapons: expected False, got None.
- 237: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected True, got None.
- 243: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected True, got None.
- 1705: nudity: expected True, got None; sexualContent: expected True, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 1709: sexualContent: expected True, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 1725: sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 4: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 5: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 10: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- 17: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- middle-finger-card: nudity: expected False, got None; sexualContent: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- thumbs-up-card: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- extremist-slogan: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected True, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- anti-hate: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- hate-symbol: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.
- cats: nudity: expected False, got None; sexualContent: expected False, got None; middleFinger: expected False, got None; hateSymbols: expected False, got None; hateWords: expected False, got None; alcohol: expected False, got None; drugs: expected False, got None; violence: expected False, got None; weapons: expected False, got None.

## Operational outcome

Original chat model restored successfully: True. Loaded model(s): qwen3:1.7b.

No filter was deployed and no Fanmass settings changed. No movie, dense crowd, small-logo or non-English claim is supported by this benchmark. Category-specific real Fanmass holdouts and independent label adjudication are required before automated moderation.
