# English structured text ranking

Updated with [Round 6](../round6/REPORT.md) (LFM2 1.2B and OLMo 2 1B added; leaders unchanged). Fourteen common checks (seven prompts repeated); historical scores retained. Moderation and languages remain separate.

| Rank | Model | Correct | JSON valid | Native tool | Median seconds |
| --- | --- | --- | --- | --- | --- |
| 1 | granite4:1b-h | 14/14 | 14/14 | True | 3.028 |
| 2 | qwen3:0.6b | 12/14 | 14/14 | True | 1.110 |
| 3 | qwen3:1.7b | 12/14 | 14/14 | True | 2.010 |
| 4 | qwen2.5:0.5b | 10/14 | 14/14 | True | 0.829 |
| 5 | hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M | 10/14 | 14/14 | True | 1.256 |
| 6 | granite3.3:2b | 10/14 | 14/14 | True | 3.107 |
| 7 | granite4:350m | 10/14 | 14/14 | True | 3.360 |
| 8 | qwen2.5-coder:0.5b | 10/14 | 14/14 | False | 0.796 |
| 9 | qwen2.5:1.5b | 8/14 | 14/14 | True | 2.066 |
| 10 | hf.co/allenai/OLMo-2-0425-1B-Instruct-GGUF:Q4_K_M | 8/14 | 14/14 | False | 1.158 |
| 11 | hf.co/LiquidAI/LFM2-1.2B-GGUF:LFM2-1.2B-Q4_K_M.gguf | 8/14 | 14/14 | False | 1.163 |
| 12 | llama3.2:1b | 8/14 | 14/14 | False | 1.633 |
| 13 | smollm2:1.7b | 8/14 | 12/14 | True | 2.140 |
| 14 | hf.co/LiquidAI/LFM2.5-350M-GGUF:Q4_K_M | 6/14 | 14/14 | True | 0.475 |
| 15 | granite3.1-moe:1b | 6/14 | 14/14 | False | 0.903 |
| 16 | hf.co/QuantFactory/EuroLLM-1.7B-Instruct-GGUF:Q4_K_M | 5/14 | 12/14 | False | 2.237 |
| 17 | gemma3:1b | 4/14 | 14/14 | False | 2.683 |
| 18 | gemma3:270m | 3/14 | 12/14 | False | 0.907 |
| 19 | smollm2:360m | 0/14 | 10/14 | False | 4.469 |
| 20 | smollm2:135m | 0/14 | 8/14 | False | 2.548 |
