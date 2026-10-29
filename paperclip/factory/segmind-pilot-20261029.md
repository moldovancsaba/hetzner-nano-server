# Segmind lane: first run on stuck drafts, 2026-10-29

The lane ([SEGMIND.md](SEGMIND.md)) was switched on at about 15:20 UTC with the default limits. The owner asked for it to be run on the ClassScout drafts stuck at `needs_more_evidence`. Those drafts are stuck because the quality review requires a name and an address.

## What was run

- A six-entity pilot, then the other stuck entities whose source is a single provider page. Tasks are children of NAR-983.
- Not queued: six aggregator, blog, city-directory or shop pages (New York Family twice, KidsDanceMap, CourseHorse, Growing Up NYC, a shop collection) and Bronx Music Hall, which had already had a paid pass that found nothing new.
- Each entity got a fresh Research Analyst task for its original source URL; the usual Content Quality Reviewer task followed. Nothing was published by this work.
- The first version of the trigger only escalated when price or opening hours were missing. The pilot showed two entities stuck on a missing name that were never escalated, so the trigger now covers name, address, price and opening hours. Those two were re-run afterwards.

## Result

| | Before | After |
| --- | --- | --- |
| Entities re-researched | 23 | 23 |
| `needs_more_evidence` | 23 | 3 (Bronx Music Hall, Tribeca Music Studio, Tam Tam: no street address on the page) |
| `ready_for_human_review` | 0 | 20 |
| All ClassScout drafts ready for review | 107 | 127 |
| `needs_more_evidence`, all drafts | 29 | 9 (six of them are the skipped aggregator pages) |

Research tasks: 25. The remote model added facts in 22, found nothing in 1 and was not triggered in 2 (the two that were re-run). Facts it added, each with a verbatim page quote: name 14, address 12, activities 11, price 8, email 4, phone 2, opening hours 2. The gain is mostly the missing name and address that blocked review, not price or hours.

## Cost

24 calls including the probe, $0.0687 in total, $0.0029 on average and $0.0046 at most; no call failed. The Segmind balance fell from 117.9988 to 117.93 credits, matching the ledger.

## Caveats

- This is not a controlled comparison: there was no second local-only pass over the same pages, so some gain may come from the pages having changed. The remote lane's own additions are counted from the run comments, and the quality reviewer re-verified every quote.
- "Ready for review" means the evidence check passed, not that the facts are right or that a listing should be published. Humans still review, and ClassScout's publication gates are unchanged.
- The ready drafts now enter the existing publication-preparation queue, which handles five a time under the automatic quality policy. At the time of writing no new publication packet had been created by this work and nothing had been written to ClassScout.
- 20 entities is a small sample taken at one moment.
