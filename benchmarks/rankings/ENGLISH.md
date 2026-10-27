# English structured-task ranking

Measured on our 4 GB CPU server; fourteen shared English checks per model. Non-English results are excluded. This does not rank broad conversational fluency or world knowledge. Within equal correctness counts, JSON validity, native tool calling and median request time determine order.

| Rank | Model | Correct | Valid JSON | Native tool | Median seconds |
| --- | --- | --- | --- | --- | --- |
| 1 | granite4:1b-h | 14/14 | 14/14 | pass | 3.03 |
| 2 | qwen3:0.6b | 12/14 | 14/14 | pass | 1.11 |
| 3 | qwen3:1.7b | 12/14 | 14/14 | pass | 2.01 |
| 4 | LFM2.5-1.2B Q4 | 10/14 | 14/14 | pass | 1.26 |
| 5 | granite3.3:2b | 10/14 | 14/14 | pass | 3.11 |
| 6 | granite4:350m | 10/14 | 14/14 | pass | 3.36 |
| 7 | qwen2.5:1.5b | 8/14 | 14/14 | pass | 2.07 |
| 8 | llama3.2:1b | 8/14 | 14/14 | fail | 1.63 |
| 9 | smollm2:1.7b | 8/14 | 12/14 | pass | 2.14 |
| 10 | granite3.1-moe:1b | 6/14 | 14/14 | fail | 0.90 |
| 11 | EuroLLM-1.7B Q4 | 5/14 | 12/14 | fail | 2.24 |
| 12 | gemma3:1b | 4/14 | 14/14 | fail | 2.68 |

Granite 4 1B Hybrid remains the structured-task leader in this sample. Qwen3 1.7B remains the deployed English chat baseline. Always-thinking candidates with a majority of empty length-limited final answers are excluded from this fast-profile ranking; their larger-budget English smoke checks are reported separately. No broad reasoning accuracy ranking is established.

[Full methodology, failures and reasoning check](../round3/REPORT.md). [Independent non-English workstream](../non-english/REPORT.md).
