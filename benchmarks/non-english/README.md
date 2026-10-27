# Independent non-English workstream

Start with REPORT.md. Current evidence covers only preliminary Hungarian examples. No language has production acceptance.

- Hungarian evidence: hungarian-results.json, extracted without changing original observations.
- English-only results: ../round2/english-results.json. Non-English scores are excluded.
- Future language runs: run.py below; each language gets its own file, model choice, dataset, acceptance and latency measurements.
- Do not combine languages, or let a language score approve/reject an English chat, structured-task or image model.
- OCR in a non-English language needs a separate language-and-image dataset; English poster results are not evidence for it.

Example optional future diagnostic (not run by this documentation change):

```sh
python3 run.py --language hu --model qwen3:1.7b --project classscout
```

This small diagnostic is not a fluency certification. Extend a separate language dataset and have a fluent reviewer assess meaning, grammar, usefulness and factual grounding. The runner saves results only, never grants approval or changes production routing. Credentials stay in the root private folder and are never written to results.
